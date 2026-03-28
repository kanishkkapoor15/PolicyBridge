from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from models.session import SessionStage
from models.documents import Document, GapItem, ConvertedClause
from models.reports import ConversionPlan, ConflictItem, FinalReport


class GraphState(TypedDict):
    session_id: str
    stage: SessionStage
    documents: list[Document]
    conflicts: list[ConflictItem]
    gaps: dict[str, list[GapItem]]  # doc_id -> gaps
    conversion_plan: ConversionPlan | None
    plan_approved: bool
    current_document_index: int
    converted_documents: dict[str, list[ConvertedClause]]  # doc_id -> clauses
    document_approvals: dict[str, bool]  # doc_id -> approved
    final_report: FinalReport | None
    chat_history: list[dict]
    error: str | None
