"""Export routes — Word document and JSON downloads."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from config import SESSIONS_DIR
from graph.checkpointer import load_session_state
from utils.export import generate_word_export, generate_json_export

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}/export")


@router.get("/docx")
async def export_docx(session_id: str):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    if not state.get("export_ready"):
        raise HTTPException(400, "Export not ready — session must be complete")

    docx_bytes = generate_word_export(state)

    # Save to disk as well
    export_dir = Path(SESSIONS_DIR) / session_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "report.docx").write_bytes(docx_bytes)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="PolicyBridge_{session_id[:8]}.docx"'},
    )


@router.get("/json")
async def export_json(session_id: str):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    json_str = generate_json_export(state)

    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="PolicyBridge_{session_id[:8]}.json"'},
    )


@router.get("/summary")
async def export_summary(session_id: str):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    if not state.get("export_ready"):
        raise HTTPException(400, "Export not ready — session must be complete")

    return state.get("final_report", {})
