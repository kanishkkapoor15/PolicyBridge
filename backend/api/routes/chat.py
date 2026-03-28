"""Chat routes — works at any session stage."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from agents.chat_agent import run_chat_agent
from graph.checkpointer import save_session_snapshot, load_session_state
from models.api import ChatRequest, ChatResponse, ChatHistoryResponse, ChatHistoryMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}/chat")


@router.post("", response_model=ChatResponse)
async def send_chat_message(session_id: str, req: ChatRequest):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    result = run_chat_agent(state, req.message)

    # Append to chat history
    chat_history = list(state.get("chat_history", []))
    now = datetime.utcnow().isoformat()
    chat_history.append({"role": "human", "content": req.message, "timestamp": now})
    chat_history.append({"role": "assistant", "content": result.get("response", ""), "timestamp": now})
    state["chat_history"] = chat_history
    save_session_snapshot(session_id, state)

    return ChatResponse(
        response=result.get("response", ""),
        suggested_actions=result.get("suggested_actions", []),
        rag_sources_used=result.get("rag_sources_used", []),
        stage=state.get("current_stage", "unknown"),
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    messages = [
        ChatHistoryMessage(
            role=m.get("role", "unknown"),
            content=m.get("content", ""),
            timestamp=m.get("timestamp", ""),
        )
        for m in state.get("chat_history", [])
    ]
    return ChatHistoryResponse(messages=messages)
