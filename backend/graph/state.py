"""PolicyBridge LangGraph state schema — single source of truth for session state."""

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class PolicyBridgeState(TypedDict):
    # Session metadata
    session_id: str
    policy_category: str  # hr_employment, data_protection, it_security, corporate_governance, health_safety
    source_jurisdiction: str  # e.g. "us_delaware", "us_california", "uk"
    target_jurisdiction: str  # always "ireland_eu" for MVP

    # Document batch
    uploaded_documents: list[dict]  # [{doc_id, filename, raw_text, doc_type}]
    current_doc_index: int  # which document we're currently processing (0-based)

    # Stage 2: Batch Analysis outputs
    intra_batch_conflicts: list[dict]  # [{doc_a, doc_b, conflict_description, severity}]
    gap_analysis: list[dict]  # per-document: [{doc_id, gaps: [{clause, issue, relevant_law, confidence}]}]
    conversion_plan: dict  # {summary, per_document_actions: [{doc_id, filename, planned_changes: []}]}
    plan_approved: bool  # auditor approval gate

    # Stage 3: Conversion outputs
    converted_documents: list[dict]  # [{doc_id, filename, original_text, converted_text, changes: [...], status}]
    current_doc_approved: bool  # per-document approval gate

    # Stage 4: Summary
    final_report: Optional[dict]  # {executive_summary, total_gaps_found, total_changes_made, compliance_score}
    outstanding_issues: list[dict]  # [{doc_id, issue, reason_requires_solicitor}]
    export_ready: bool

    # Chat
    chat_history: Annotated[list, add_messages]  # full session chat across all stages

    # Control flow
    current_stage: str  # ingestion | analysis | awaiting_plan_approval | conversion | awaiting_doc_approval | summary | complete
    agent_messages: list[str]  # log of agent actions shown to auditor in real time
    errors: list[str]
