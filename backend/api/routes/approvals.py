"""Plan and document approval routes."""

import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

from graph.checkpointer import save_session_snapshot, load_session_state
from graph.workflow import get_graph
from langgraph.types import Command
from models.api import ApprovalRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}")


def _resume_graph(session_id: str, resume_value: dict):
    """Background task: resume graph from an interrupt with the given value."""
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}

        result = None
        for event in graph.stream(Command(resume=resume_value), config, stream_mode="values"):
            result = event
            save_session_snapshot(session_id, event)

        if result:
            save_session_snapshot(session_id, result)
            logger.info(f"Graph resumed for {session_id}: stage={result.get('current_stage')}")
    except Exception as e:
        logger.error(f"Graph resume failed for {session_id}: {e}")
        state = load_session_state(session_id) or {}
        state["errors"] = state.get("errors", []) + [f"Resume failed: {str(e)}"]
        save_session_snapshot(session_id, state)


@router.post("/approve-plan")
async def approve_plan(session_id: str, req: ApprovalRequest, background_tasks: BackgroundTasks):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    if state.get("current_stage") != "awaiting_plan_approval":
        raise HTTPException(400, f"Session is not awaiting plan approval (stage: {state.get('current_stage')})")

    resume_value = {"approved": req.approved}
    if req.feedback:
        resume_value["feedback"] = req.feedback

    background_tasks.add_task(_resume_graph, session_id, resume_value)

    action = "approved" if req.approved else "rejected"
    return {"status": f"plan_{action}", "session_id": session_id}


@router.post("/approve-document")
async def approve_document(session_id: str, req: ApprovalRequest, background_tasks: BackgroundTasks):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    if state.get("current_stage") != "awaiting_doc_approval":
        raise HTTPException(400, f"Session is not awaiting doc approval (stage: {state.get('current_stage')})")

    resume_value = {"approved": req.approved}
    if req.feedback:
        resume_value["feedback"] = req.feedback

    background_tasks.add_task(_resume_graph, session_id, resume_value)

    action = "approved" if req.approved else "rejected"
    idx = state.get("current_doc_index", 0)
    return {"status": f"document_{action}", "session_id": session_id, "doc_index": idx}
