from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ConflictItem(BaseModel):
    document_a: str
    document_b: str
    description: str
    recommendation: str


class PlanAction(BaseModel):
    document_id: str
    document_name: str
    actions: list[str]
    rationale: str


class ConversionPlan(BaseModel):
    session_id: str
    conflicts: list[ConflictItem] = Field(default_factory=list)
    gap_summary: str = ""
    plan_actions: list[PlanAction] = Field(default_factory=list)
    overall_risk_assessment: str = ""


class OutstandingIssue(BaseModel):
    document_name: str
    issue: str
    requires_solicitor: bool = False
    notes: str = ""


class FinalReport(BaseModel):
    session_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_documents: int = 0
    total_gaps_found: int = 0
    total_changes_made: int = 0
    compliance_score: int = 0
    summary: str = ""
    outstanding_issues: list[OutstandingIssue] = Field(default_factory=list)
    audit_trail: list[dict] = Field(default_factory=list)
