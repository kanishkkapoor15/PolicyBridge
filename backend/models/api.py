"""Pydantic request/response models for API routes."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Requests ──

class CreateSessionRequest(BaseModel):
    policy_category: str = Field(..., description="HR/Employment, Data Protection, IT/Security, Corporate Governance, Health & Safety")
    source_jurisdiction: str = Field(..., description="e.g. US-Delaware, US-California, UK")


class ApprovalRequest(BaseModel):
    approved: bool
    feedback: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


# ── Responses ──

class SessionCreatedResponse(BaseModel):
    session_id: str
    policy_category: str
    source_jurisdiction: str
    target_jurisdiction: str = "Ireland/EU"
    current_stage: str
    created_at: str


class DocumentUploadedItem(BaseModel):
    doc_id: str
    filename: str
    size_bytes: int
    text_length: int


class DocumentUploadResponse(BaseModel):
    uploaded: list[DocumentUploadedItem]
    total_documents: int


class DocumentSummaryItem(BaseModel):
    doc_id: str
    filename: str
    doc_type: Optional[str] = None
    status: str = "uploaded"


class SessionSummaryResponse(BaseModel):
    session_id: str
    current_stage: str
    policy_category: str
    source_jurisdiction: str
    documents: list[DocumentSummaryItem]
    plan_approved: bool
    conversion_plan: Optional[dict] = None
    converted_count: int
    total_documents: int
    gap_analysis: Optional[list[dict]] = None
    converted_documents: Optional[list[dict]] = None
    agent_messages: list[str]
    errors: list[str]
    export_ready: bool
    final_report: Optional[dict] = None


class SessionListItem(BaseModel):
    session_id: str
    policy_category: str
    source_jurisdiction: str
    current_stage: str
    document_count: int
    created_at: str


class AnalysisStartedResponse(BaseModel):
    status: str = "analysis_started"
    session_id: str


class ChatResponse(BaseModel):
    response: str
    suggested_actions: list[str] = Field(default_factory=list)
    rag_sources_used: list[str] = Field(default_factory=list)
    stage: str


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
