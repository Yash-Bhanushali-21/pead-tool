"""
FastAPI app: streamed chat with the PydanticAI research coordinator.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Project root on path (run: uvicorn server.app:app from repo root)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from src.agent.agents import build_coordinator_agent, build_synthesis_agent
from src.agent.deps import ResearchDeps
from src.agent.streaming import chat_messages_to_history, stream_research_chat
from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.config import CONFIG, config
from src.persistence.sqlite_chat import ChatStore, accumulate_stream_line
from src.persistence.sqlite_news_articles import get_news_article_store
from server.news_routes import router as news_router
from server.tools_routes import router as tools_router


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    coordinator_model: Optional[str] = None
    synthesis_model: Optional[str] = None
    session_id: Optional[str] = Field(
        None,
        description="Client-owned UUID; server creates one if omitted when persist=true.",
    )
    persist: bool = Field(
        True,
        description="If true and CHAT_PERSIST_ENABLED, store this turn in SQLite.",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pead_analyzer = PEADAnalyzer(use_cache=True)
    store = ChatStore(CONFIG["CHAT_SQLITE_PATH"])
    store.init_schema()
    app.state.chat_store = store
    news_path = CONFIG.get("NEWS_SQLITE_PATH") or CONFIG["CHAT_SQLITE_PATH"]
    get_news_article_store(news_path)
    yield


app = FastAPI(title="PEAD Research Agent", version="0.1.0", lifespan=lifespan)
app.include_router(tools_router)
app.include_router(news_router)

_cors = CONFIG["PEAD_CORS_ORIGINS"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "agent_model": config.AGENT_MODEL,
        "chat_persist_enabled": CONFIG.get("CHAT_PERSIST_ENABLED", True),
        "chat_sqlite_path": CONFIG.get("CHAT_SQLITE_PATH"),
        "news_sqlite_path": CONFIG.get("NEWS_SQLITE_PATH") or CONFIG.get("CHAT_SQLITE_PATH"),
    }


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, request: Request):
    if not CONFIG.get("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set; the agent requires it for PydanticAI models.",
        )
    msgs = [m.model_dump() for m in body.messages]
    out_base = ROOT / "output" / config.AGENT_OUTPUT_SUBDIR
    out_base.mkdir(parents=True, exist_ok=True)

    deps = ResearchDeps(
        analyzer=request.app.state.pead_analyzer,
        output_base=out_base,
    )

    persist = bool(body.persist and CONFIG.get("CHAT_PERSIST_ENABLED", True))
    store: ChatStore = request.app.state.chat_store
    sid_raw = (body.session_id or "").strip() or None
    session_id: Optional[str] = sid_raw
    if persist:
        session_id = sid_raw or str(uuid.uuid4())
    turn_id: Optional[int] = None
    if persist and session_id:
        store.ensure_session(session_id, source="chat")
        user_text = (msgs[-1].get("content") or "").strip()
        turn_id = store.append_turn_user(session_id, user_text)

    async def event_stream():
        text_parts: list[str] = []
        tool_events: list[dict] = []
        final_done: list[Optional[str]] = [None]
        err_holder: list[Optional[str]] = [None]
        try:
            if persist and session_id:
                ack = json.dumps({"type": "session_ack", "session_id": session_id})
                yield f"data: {ack}\n\n"

            async for line in stream_research_chat(
                deps=deps,
                messages=msgs,
                coordinator_model=body.coordinator_model or config.AGENT_MODEL,
                synthesis_model=body.synthesis_model or config.AGENT_SYNTHESIS_MODEL,
            ):
                payload = line.strip()
                if payload:
                    accumulate_stream_line(
                        payload,
                        text_acc=text_parts,
                        tool_events=tool_events,
                        final_from_done=final_done,
                        error_out=err_holder,
                    )
                    yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            err_holder[0] = str(e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if persist and session_id and turn_id is not None:
                assistant_text = final_done[0]
                if assistant_text is None:
                    assistant_text = "".join(text_parts) if text_parts else None
                trace_str = json.dumps(tool_events, default=str) if tool_events else None
                def _complete():
                    store.complete_turn(
                        turn_id,
                        assistant_content=assistant_text,
                        tool_trace_json=trace_str,
                        error=err_holder[0],
                    )
                await asyncio.to_thread(_complete)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat_complete(body: ChatRequest, request: Request):
    """Non-streaming: single coordinator run (same tools as streaming)."""
    if not CONFIG.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set.")

    out_base = ROOT / "output" / config.AGENT_OUTPUT_SUBDIR
    out_base.mkdir(parents=True, exist_ok=True)
    deps = ResearchDeps(analyzer=request.app.state.pead_analyzer, output_base=out_base)
    synth = build_synthesis_agent(model=body.synthesis_model or config.AGENT_SYNTHESIS_MODEL)
    coord = build_coordinator_agent(
        synth, model=body.coordinator_model or config.AGENT_MODEL
    )
    hist, user_prompt = chat_messages_to_history([m.model_dump() for m in body.messages])
    result = await coord.run(user_prompt, message_history=hist, deps=deps)
    out_text = result.output if isinstance(result.output, str) else str(result.output)

    persist = bool(body.persist and CONFIG.get("CHAT_PERSIST_ENABLED", True))
    sid = (body.session_id or "").strip() or None
    if persist:
        sid = sid or str(uuid.uuid4())
        store: ChatStore = request.app.state.chat_store
        store.ensure_session(sid, source="chat")
        user_text = (body.messages[-1].content or "").strip()
        store.insert_complete_turn(sid, user_text, out_text)

    resp: dict = {"role": "assistant", "content": out_text}
    if persist and sid:
        resp["session_id"] = sid
    return resp


@app.get("/api/chat/sessions")
def list_chat_sessions(request: Request, limit: int = 50):
    """List recent chat sessions (SQLite). For analytics / export; no auth in dev."""
    store: ChatStore = request.app.state.chat_store
    rows = store.list_sessions(min(limit, 200))
    return {"sessions": rows}


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(request: Request, session_id: str):
    """Return all turns for a session (user + assistant + tool trace)."""
    store: ChatStore = request.app.state.chat_store
    sid = session_id.strip()
    if not store.has_session(sid):
        raise HTTPException(status_code=404, detail="Session not found.")
    turns = store.get_session_turns(sid)
    return {"session_id": sid, "turns": turns}
