"""Session management routes."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config import SESSIONS_DIR
from graph.checkpointer import save_session_snapshot, load_session_state
from models.api import (
    CreateSessionRequest,
    SessionCreatedResponse,
    SessionSummaryResponse,
    SessionListItem,
    DocumentSummaryItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions")

# Category name normalisation
CATEGORY_MAP = {
    "hr/employment": "hr_employment",
    "hr_employment": "hr_employment",
    "data protection": "data_protection",
    "data_protection": "data_protection",
    "it/security": "it_security",
    "it_security": "it_security",
    "corporate governance": "corporate_governance",
    "corporate_governance": "corporate_governance",
    "health & safety": "health_safety",
    "health_safety": "health_safety",
}

JURISDICTION_MAP = {
    "us-delaware": "us_delaware",
    "us_delaware": "us_delaware",
    "us-california": "us_california",
    "us_california": "us_california",
    "uk": "uk",
    "us-federal": "us_federal",
    "us_federal": "us_federal",
    "us-new york": "us_new_york",
    "us_new_york": "us_new_york",
}


def _normalise(value: str, mapping: dict) -> str:
    return mapping.get(value.lower().strip(), value.lower().replace(" ", "_").replace("-", "_"))


def _build_initial_state(session_id: str, category: str, jurisdiction: str) -> dict:
    return {
        "session_id": session_id,
        "policy_category": category,
        "source_jurisdiction": jurisdiction,
        "target_jurisdiction": "ireland_eu",
        "uploaded_documents": [],
        "current_doc_index": 0,
        "intra_batch_conflicts": [],
        "gap_analysis": [],
        "conversion_plan": {},
        "plan_approved": False,
        "converted_documents": [],
        "current_doc_approved": False,
        "final_report": None,
        "outstanding_issues": [],
        "export_ready": False,
        "chat_history": [],
        "current_stage": "initialization",
        "agent_messages": [],
        "errors": [],
    }


def _state_to_summary(state: dict) -> dict:
    docs = state.get("uploaded_documents", [])
    converted = state.get("converted_documents", [])

    doc_summaries = []
    converted_ids = {d.get("doc_id") for d in converted}
    for d in docs:
        status = "uploaded"
        if d["doc_id"] in converted_ids:
            status = "converted"
        elif d.get("doc_type"):
            status = "analysed"
        doc_summaries.append(DocumentSummaryItem(
            doc_id=d["doc_id"],
            filename=d["filename"],
            doc_type=d.get("doc_type"),
            status=status,
        ))

    return SessionSummaryResponse(
        session_id=state.get("session_id", ""),
        current_stage=state.get("current_stage", "unknown"),
        policy_category=state.get("policy_category", ""),
        source_jurisdiction=state.get("source_jurisdiction", ""),
        documents=doc_summaries,
        plan_approved=state.get("plan_approved", False),
        conversion_plan=state.get("conversion_plan") or None,
        converted_count=len(converted),
        total_documents=len(docs),
        gap_analysis=state.get("gap_analysis") or None,
        converted_documents=converted or None,
        agent_messages=state.get("agent_messages", []),
        errors=state.get("errors", []),
        export_ready=state.get("export_ready", False),
        final_report=state.get("final_report") or None,
    ).model_dump()


@router.post("", response_model=SessionCreatedResponse)
async def create_session(req: CreateSessionRequest):
    session_id = str(uuid.uuid4())
    category = _normalise(req.policy_category, CATEGORY_MAP)
    jurisdiction = _normalise(req.source_jurisdiction, JURISDICTION_MAP)

    state = _build_initial_state(session_id, category, jurisdiction)
    now = datetime.utcnow().isoformat()
    state["created_at"] = now

    # Persist
    save_session_snapshot(session_id, state)

    logger.info(f"Created session {session_id}: {category}, {jurisdiction}")
    return SessionCreatedResponse(
        session_id=session_id,
        policy_category=category,
        source_jurisdiction=jurisdiction,
        target_jurisdiction="Ireland/EU",
        current_stage="initialization",
        created_at=now,
    )


@router.get("/{session_id}")
async def get_session(session_id: str):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")
    return _state_to_summary(state)


@router.get("")
async def list_sessions():
    sessions_path = Path(SESSIONS_DIR)
    items = []
    if sessions_path.exists():
        for session_dir in sorted(sessions_path.iterdir(), reverse=True):
            if session_dir.is_dir():
                state_file = session_dir / "state.json"
                if state_file.exists():
                    try:
                        state = json.loads(state_file.read_text())
                        items.append(SessionListItem(
                            session_id=state.get("session_id", session_dir.name),
                            policy_category=state.get("policy_category", ""),
                            source_jurisdiction=state.get("source_jurisdiction", ""),
                            current_stage=state.get("current_stage", "unknown"),
                            document_count=len(state.get("uploaded_documents", [])),
                            created_at=state.get("created_at", ""),
                        ))
                    except (json.JSONDecodeError, KeyError):
                        pass
    return {"sessions": [s.model_dump() for s in items]}
