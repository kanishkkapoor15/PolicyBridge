"""LangGraph workflow definition with all nodes, edges, and interrupt points."""

import logging

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt, Command

from graph.state import PolicyBridgeState
from graph.checkpointer import get_checkpointer, save_session_snapshot
from agents.ingestion_agent import run_ingestion_agent
from agents.conflict_agent import run_conflict_agent
from agents.gap_analysis_agent import run_gap_analysis_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node implementations — Agents 1-3 are real, rest are stubs until Step 5B
# ---------------------------------------------------------------------------

def ingest_documents(state: PolicyBridgeState) -> dict:
    """Process uploaded files: extract text and classify document type."""
    return run_ingestion_agent(state)


def detect_conflicts(state: PolicyBridgeState) -> dict:
    """Cross-reference all documents in the batch for contradictions."""
    return run_conflict_agent(state)


def analyze_gaps(state: PolicyBridgeState) -> dict:
    """RAG-powered gap analysis comparing docs against Irish/EU legal corpus."""
    return run_gap_analysis_agent(state)


def generate_plan(state: PolicyBridgeState) -> dict:
    """Synthesise gap analysis into a human-readable conversion plan."""
    docs = state.get("uploaded_documents", [])
    plan = {
        "summary": "Conversion plan for batch of documents (stub)",
        "per_document_actions": [
            {
                "doc_id": doc["doc_id"],
                "filename": doc["filename"],
                "planned_changes": ["Review and convert to Irish/EU compliance (stub)"],
            }
            for doc in docs
        ],
    }
    msg = f"[generate_plan] conversion plan ready for {len(docs)} documents"
    logger.info(msg)
    return {
        "conversion_plan": plan,
        "current_stage": "awaiting_plan_approval",
        "agent_messages": state.get("agent_messages", []) + [msg],
    }


def human_plan_approval(state: PolicyBridgeState) -> dict:
    """Interrupt: wait for auditor to approve or reject the conversion plan."""
    logger.info("[human_plan_approval] awaiting auditor input")
    approval = interrupt({
        "type": "plan_approval",
        "message": "Please review the conversion plan and approve or request changes.",
        "conversion_plan": state.get("conversion_plan", {}),
    })
    approved = approval.get("approved", False) if isinstance(approval, dict) else bool(approval)
    return {
        "plan_approved": approved,
        "current_stage": "conversion" if approved else "awaiting_plan_approval",
        "agent_messages": state.get("agent_messages", []) + [
            f"[human_plan_approval] plan {'approved' if approved else 'rejected'}"
        ],
    }


def convert_document(state: PolicyBridgeState) -> dict:
    """Convert the current document (by current_doc_index) to Irish/EU compliance."""
    idx = state.get("current_doc_index", 0)
    docs = state.get("uploaded_documents", [])
    doc = docs[idx] if idx < len(docs) else {"doc_id": "unknown", "filename": "unknown"}

    converted = {
        "doc_id": doc["doc_id"],
        "filename": doc["filename"],
        "original_text": doc.get("raw_text", ""),
        "converted_text": f"[Converted version of {doc['filename']}] (stub)",
        "changes": [
            {
                "original_clause": "Original clause text (stub)",
                "new_clause": "Converted clause text (stub)",
                "legal_citation": "GDPR Article 5 (stub)",
                "confidence": 85,
            }
        ],
        "status": "converted",
    }

    existing = list(state.get("converted_documents", []))
    # Replace if re-converting same doc, otherwise append
    replaced = False
    for i, c in enumerate(existing):
        if c["doc_id"] == doc["doc_id"]:
            existing[i] = converted
            replaced = True
            break
    if not replaced:
        existing.append(converted)

    msg = f"[convert_document] processing doc {idx + 1}/{len(docs)}: {doc['filename']}"
    logger.info(msg)
    return {
        "converted_documents": existing,
        "current_stage": "awaiting_doc_approval",
        "agent_messages": state.get("agent_messages", []) + [msg],
    }


def human_doc_approval(state: PolicyBridgeState) -> dict:
    """Interrupt: wait for auditor to approve or reject the converted document."""
    idx = state.get("current_doc_index", 0)
    logger.info(f"[human_doc_approval] awaiting auditor input for doc {idx + 1}")
    approval = interrupt({
        "type": "doc_approval",
        "message": "Please review the converted document and approve or reject.",
        "doc_index": idx,
    })
    approved = approval.get("approved", False) if isinstance(approval, dict) else bool(approval)
    return {
        "current_doc_approved": approved,
        "agent_messages": state.get("agent_messages", []) + [
            f"[human_doc_approval] doc {idx + 1} {'approved' if approved else 'rejected'}"
        ],
    }


def advance_or_finish(state: PolicyBridgeState) -> dict:
    """After doc approval, advance the index if approved, or leave it for re-conversion."""
    approved = state.get("current_doc_approved", False)
    if approved:
        new_index = state.get("current_doc_index", 0) + 1
        total = len(state.get("uploaded_documents", []))
        if new_index >= total:
            msg = f"[advance_or_finish] all {total} documents processed"
            logger.info(msg)
            return {
                "current_doc_index": new_index,
                "current_doc_approved": False,
                "current_stage": "summary",
                "agent_messages": state.get("agent_messages", []) + [msg],
            }
        msg = f"[advance_or_finish] {total - new_index} more document(s) to process"
        logger.info(msg)
        return {
            "current_doc_index": new_index,
            "current_doc_approved": False,
            "current_stage": "conversion",
            "agent_messages": state.get("agent_messages", []) + [msg],
        }
    # Rejected — keep same index so convert_document re-processes it
    return {"current_doc_approved": False, "current_stage": "conversion"}


def generate_summary(state: PolicyBridgeState) -> dict:
    """Generate final report, outstanding issues, and mark session complete."""
    docs = state.get("uploaded_documents", [])
    converted = state.get("converted_documents", [])
    report = {
        "executive_summary": f"Completed conversion of {len(converted)} documents (stub)",
        "total_gaps_found": sum(len(g.get("gaps", [])) for g in state.get("gap_analysis", [])),
        "total_changes_made": sum(len(c.get("changes", [])) for c in converted),
        "compliance_score": 85,
    }
    msg = "[generate_summary] session complete"
    logger.info(msg)
    return {
        "final_report": report,
        "outstanding_issues": [],
        "export_ready": True,
        "current_stage": "complete",
        "agent_messages": state.get("agent_messages", []) + [msg],
    }


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------

def should_continue_conversion(state: PolicyBridgeState) -> str:
    """Decide whether to convert next doc, re-convert current, or finish."""
    stage = state.get("current_stage", "")
    if stage == "summary":
        return "generate_summary"
    # If we're still in conversion, check if index is within bounds
    idx = state.get("current_doc_index", 0)
    total = len(state.get("uploaded_documents", []))
    if idx < total:
        return "convert_next"
    return "generate_summary"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Build the PolicyBridge StateGraph (uncompiled)."""
    graph = StateGraph(PolicyBridgeState)

    # Add nodes
    graph.add_node("ingest_documents", ingest_documents)
    graph.add_node("detect_conflicts", detect_conflicts)
    graph.add_node("analyze_gaps", analyze_gaps)
    graph.add_node("generate_plan", generate_plan)
    graph.add_node("human_plan_approval", human_plan_approval)
    graph.add_node("convert_document", convert_document)
    graph.add_node("human_doc_approval", human_doc_approval)
    graph.add_node("advance_or_finish", advance_or_finish)
    graph.add_node("generate_summary", generate_summary)

    # Linear flow: START → ingestion → conflict → gaps → plan → approval gate
    graph.set_entry_point("ingest_documents")
    graph.add_edge("ingest_documents", "detect_conflicts")
    graph.add_edge("detect_conflicts", "analyze_gaps")
    graph.add_edge("analyze_gaps", "generate_plan")
    graph.add_edge("generate_plan", "human_plan_approval")

    # After plan approval → start converting
    graph.add_edge("human_plan_approval", "convert_document")

    # After conversion → doc approval gate
    graph.add_edge("convert_document", "human_doc_approval")

    # After doc approval → advance index and check
    graph.add_edge("human_doc_approval", "advance_or_finish")

    # Conditional: more docs, retry, or finish
    graph.add_conditional_edges(
        "advance_or_finish",
        should_continue_conversion,
        {
            "convert_next": "convert_document",
            "retry_conversion": "convert_document",
            "generate_summary": "generate_summary",
        },
    )

    graph.add_edge("generate_summary", END)

    return graph


_compiled_graph = None


def get_graph():
    """Return a singleton compiled graph with checkpointer and interrupt points."""
    global _compiled_graph
    if _compiled_graph is None:
        checkpointer = get_checkpointer()
        graph = build_graph()
        _compiled_graph = graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_plan_approval", "human_doc_approval"],
        )
    return _compiled_graph
