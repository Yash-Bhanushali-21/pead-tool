"""
FastAPI app: streamed chat with the PydanticAI research coordinator.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Project root on path (run: uvicorn server.app:app from repo root)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from src.agent.agents import build_coordinator_agent, build_synthesis_agent
from src.agent.deps import ResearchDeps
from src.agent.streaming import chat_messages_to_history, stream_research_chat
from src.analysis.pead_analyzer import PEADAnalyzer
from src.config.settings import config
from server.tools_routes import router as tools_router


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    coordinator_model: Optional[str] = None
    synthesis_model: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pead_analyzer = PEADAnalyzer(use_cache=True)
    yield


app = FastAPI(title="PEAD Research Agent", version="0.1.0", lifespan=lifespan)
app.include_router(tools_router)

_cors = os.environ.get("PEAD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "agent_model": config.AGENT_MODEL}


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest):
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set; the agent requires it for PydanticAI models.",
        )
    msgs = [m.model_dump() for m in body.messages]
    out_base = ROOT / "output" / config.AGENT_OUTPUT_SUBDIR
    out_base.mkdir(parents=True, exist_ok=True)

    deps = ResearchDeps(
        analyzer=app.state.pead_analyzer,
        output_base=out_base,
    )

    async def event_stream():
        try:
            async for line in stream_research_chat(
                deps=deps,
                messages=msgs,
                coordinator_model=body.coordinator_model or config.AGENT_MODEL,
                synthesis_model=body.synthesis_model or config.AGENT_SYNTHESIS_MODEL,
            ):
                payload = line.strip()
                if payload:
                    yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {{\"type\":\"error\",\"message\":{__import__('json').dumps(str(e))}}}\n\n"

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
async def chat_complete(body: ChatRequest):
    """Non-streaming: single coordinator run (same tools as streaming)."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not set.")

    out_base = ROOT / "output" / config.AGENT_OUTPUT_SUBDIR
    out_base.mkdir(parents=True, exist_ok=True)
    deps = ResearchDeps(analyzer=app.state.pead_analyzer, output_base=out_base)
    synth = build_synthesis_agent(model=body.synthesis_model or config.AGENT_SYNTHESIS_MODEL)
    coord = build_coordinator_agent(
        synth, model=body.coordinator_model or config.AGENT_MODEL
    )
    hist, user_prompt = chat_messages_to_history([m.model_dump() for m in body.messages])
    result = await coord.run(user_prompt, message_history=hist, deps=deps)
    return {"role": "assistant", "content": result.output}
