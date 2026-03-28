"""SSE streaming route for real-time agent progress."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from graph.checkpointer import load_session_state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sessions/{session_id}/stream")
async def session_stream(session_id: str, request: Request):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    async def event_generator():
        last_message_count = 0
        last_stage = ""
        stale_count = 0

        while True:
            if await request.is_disconnected():
                break

            state = load_session_state(session_id)
            if not state:
                yield {"event": "error", "data": json.dumps({"message": "Session not found"})}
                break

            messages = state.get("agent_messages", [])
            current_stage = state.get("current_stage", "")

            # Send new agent messages
            if len(messages) > last_message_count:
                for msg in messages[last_message_count:]:
                    yield {"event": "agent_message", "data": json.dumps({"message": msg})}
                last_message_count = len(messages)
                stale_count = 0

            # Send stage changes
            if current_stage != last_stage:
                yield {
                    "event": "stage_update",
                    "data": json.dumps({
                        "stage": current_stage,
                        "converted_count": len(state.get("converted_documents", [])),
                        "total_documents": len(state.get("uploaded_documents", [])),
                    }),
                }
                last_stage = current_stage
                stale_count = 0

            # Send approval notifications
            if current_stage == "awaiting_plan_approval":
                yield {
                    "event": "awaiting_approval",
                    "data": json.dumps({
                        "type": "plan_approval",
                        "conversion_plan": state.get("conversion_plan", {}),
                    }),
                }

            elif current_stage == "awaiting_doc_approval":
                idx = state.get("current_doc_index", 0)
                converted = state.get("converted_documents", [])
                current_doc = converted[-1] if converted else {}
                yield {
                    "event": "awaiting_approval",
                    "data": json.dumps({
                        "type": "doc_approval",
                        "doc_index": idx,
                        "filename": current_doc.get("filename", ""),
                        "total_changes": current_doc.get("total_changes", 0),
                    }),
                }

            # Session complete
            if current_stage == "complete":
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "export_ready": True,
                        "final_report": state.get("final_report", {}),
                    }),
                }
                break

            # Timeout after 30 min of no changes
            stale_count += 1
            if stale_count > 1800:
                yield {"event": "timeout", "data": json.dumps({"message": "Stream timed out"})}
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
