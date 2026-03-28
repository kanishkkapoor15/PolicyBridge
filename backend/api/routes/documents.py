"""Document upload and analysis trigger routes."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks

from config import SESSIONS_DIR
from graph.checkpointer import save_session_snapshot, load_session_state
from graph.workflow import get_graph
from utils.document_parser import parse_document
from models.api import DocumentUploadResponse, DocumentUploadedItem, AnalysisStartedResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}")


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_documents(session_id: str, files: list[UploadFile] = File(...)):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    uploads_dir = Path(SESSIONS_DIR) / session_id / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    uploaded_items = []
    docs = list(state.get("uploaded_documents", []))

    for file in files:
        # Validate file type
        suffix = Path(file.filename or "unknown").suffix.lower()
        if suffix not in (".pdf", ".docx", ".doc", ".txt", ".md"):
            raise HTTPException(400, f"Unsupported file type: {suffix}. Accepted: .pdf, .docx, .txt")

        # Save raw file
        doc_id = str(uuid.uuid4())
        file_path = uploads_dir / (file.filename or f"{doc_id}{suffix}")
        content = await file.read()
        file_path.write_bytes(content)

        # Parse text
        raw_text = parse_document(str(file_path))

        docs.append({
            "doc_id": doc_id,
            "filename": file.filename or f"document{suffix}",
            "raw_text": raw_text,
            "file_path": str(file_path),
        })

        uploaded_items.append(DocumentUploadedItem(
            doc_id=doc_id,
            filename=file.filename or f"document{suffix}",
            size_bytes=len(content),
            text_length=len(raw_text),
        ))

        logger.info(f"Uploaded {file.filename}: {len(content)} bytes, {len(raw_text)} chars text")

    state["uploaded_documents"] = docs
    save_session_snapshot(session_id, state)

    return DocumentUploadResponse(
        uploaded=uploaded_items,
        total_documents=len(docs),
    )


def _run_analysis(session_id: str, state: dict):
    """Background task: run the graph from START to the first interrupt."""
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}

        state["current_stage"] = "analysis"
        save_session_snapshot(session_id, state)

        # Stream through graph until first interrupt
        result = None
        for event in graph.stream(state, config, stream_mode="values"):
            result = event
            # Persist after each node so SSE can pick it up
            save_session_snapshot(session_id, event)

        if result:
            save_session_snapshot(session_id, result)
            logger.info(f"Analysis complete for {session_id}: stage={result.get('current_stage')}")
    except Exception as e:
        logger.error(f"Analysis failed for {session_id}: {e}")
        state["errors"] = state.get("errors", []) + [f"Analysis pipeline failed: {str(e)}"]
        state["current_stage"] = "error"
        save_session_snapshot(session_id, state)


@router.post("/analyse", response_model=AnalysisStartedResponse)
async def trigger_analysis(session_id: str, background_tasks: BackgroundTasks):
    state = load_session_state(session_id)
    if not state:
        raise HTTPException(404, f"Session {session_id} not found")

    if not state.get("uploaded_documents"):
        raise HTTPException(400, "No documents uploaded yet")

    background_tasks.add_task(_run_analysis, session_id, state)
    return AnalysisStartedResponse(session_id=session_id)
