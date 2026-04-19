"""
Map PydanticAI stream events to JSON-serializable chunks for SSE / UI.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    TextPartDelta,
    ThinkingPartDelta,
    ToolCallPartDelta,
)

from src.agent.agents import build_coordinator_agent, build_synthesis_agent
from src.agent.deps import ResearchDeps
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart


def _json_line(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False) + "\n"


def augment_latest_user_message(
    messages: List[Dict[str, str]],
    memory_block: Optional[str],
) -> List[Dict[str, str]]:
    """
    Prepend Mem0 (or similar) context to the latest user message only.
    Keeps a clear delimiter so the model can separate retrieved notes from the user ask.
    """
    if not memory_block or not messages:
        return messages
    out: List[Dict[str, str]] = [dict(m) for m in messages]
    last = dict(out[-1])
    base = (last.get("content") or "").strip()
    last["content"] = f"{memory_block}\n\n---\n\nUser message:\n{base}"
    out[-1] = last
    return out


def chat_messages_to_history(
    messages: List[Dict[str, str]],
) -> tuple[Optional[List[ModelMessage]], str]:
    """
    Split OpenAI-style messages into pydantic-ai history + latest user prompt.
    Last message must be role=user.
    """
    if not messages:
        raise ValueError("messages empty")
    last = messages[-1]
    if last.get("role") != "user":
        raise ValueError("last message must be user")
    user_prompt = (last.get("content") or "").strip()
    prior = messages[:-1]
    history: List[ModelMessage] = []
    for m in prior:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            history.append(ModelResponse(parts=[TextPart(content=content)]))
        else:
            continue
    return (history if history else None), user_prompt


async def stream_research_chat(
    *,
    deps: ResearchDeps,
    messages: List[Dict[str, str]],
    coordinator_model: Optional[str] = None,
    synthesis_model: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Yields newline-delimited JSON events (one JSON object per line) for HTTP streaming.
    """
    synthesis = build_synthesis_agent(model=synthesis_model)
    coordinator = build_coordinator_agent(synthesis, model=coordinator_model)

    hist, user_prompt = chat_messages_to_history(messages)

    try:
        async for event in coordinator.run_stream_events(
            user_prompt,
            message_history=hist,
            deps=deps,
        ):
            for line in _serialize_event(event):
                yield line
    except Exception as e:
        yield _json_line({"type": "error", "message": str(e)})


def _serialize_event(event: Union[AgentStreamEvent, AgentRunResultEvent]) -> List[str]:
    lines: List[str] = []
    if isinstance(event, PartDeltaEvent):
        d = event.delta
        if isinstance(d, TextPartDelta):
            if d.content_delta:
                lines.append(_json_line({"type": "text_delta", "content": d.content_delta}))
        elif isinstance(d, ThinkingPartDelta):
            if getattr(d, "content_delta", None):
                lines.append(
                    _json_line({"type": "thinking_delta", "content": d.content_delta})
                )
        elif isinstance(d, ToolCallPartDelta):
            lines.append(
                _json_line(
                    {
                        "type": "tool_call_delta",
                        "index": event.index,
                        "args_delta": getattr(d, "args_delta", None),
                    }
                )
            )
    elif isinstance(event, FunctionToolCallEvent):
        part = event.part
        tool_name = getattr(part, "tool_name", "") or ""
        args = getattr(part, "args", None)
        lines.append(
            _json_line(
                {
                    "type": "tool_call",
                    "tool_name": str(tool_name),
                    "args": args,
                    "tool_call_id": getattr(part, "tool_call_id", None),
                }
            )
        )
    elif isinstance(event, FunctionToolResultEvent):
        content = getattr(event.result, "content", "")
        preview = str(content)[:2000]
        lines.append(
            _json_line(
                {
                    "type": "tool_result",
                    "tool_call_id": event.tool_call_id,
                    "content_preview": preview,
                }
            )
        )
    elif isinstance(event, AgentRunResultEvent):
        out = event.result.output
        lines.append(
            _json_line(
                {
                    "type": "done",
                    "output": out if isinstance(out, str) else str(out),
                }
            )
        )
    return lines
