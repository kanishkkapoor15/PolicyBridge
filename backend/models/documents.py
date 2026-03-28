from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    ANALYZED = "analyzed"
    CONVERTING = "converting"
    CONVERTED = "converted"
    APPROVED = "approved"
    REJECTED = "rejected"


class GapItem(BaseModel):
    clause_reference: str
    original_text: str
    issue_description: str
    legal_citation: str
    severity: str  # "high", "medium", "low"
    confidence_score: int = Field(ge=0, le=100)


class ConvertedClause(BaseModel):
    clause_reference: str
    original_text: str
    converted_text: str
    change_description: str
    legal_citation: str
    confidence_score: int = Field(ge=0, le=100)


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    filename: str
    file_path: str
    document_type: Optional[str] = None
    extracted_text: Optional[str] = None
    status: DocumentStatus = DocumentStatus.UPLOADED
    gaps: list[GapItem] = Field(default_factory=list)
    converted_clauses: list[ConvertedClause] = Field(default_factory=list)
    converted_full_text: Optional[str] = None
    auditor_notes: list[str] = Field(default_factory=list)
