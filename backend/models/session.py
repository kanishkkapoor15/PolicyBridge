from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid


class PolicyCategory(str, Enum):
    HR_EMPLOYMENT = "hr_employment"
    DATA_PROTECTION = "data_protection"
    IT_SECURITY = "it_security"
    CORPORATE_GOVERNANCE = "corporate_governance"
    HEALTH_SAFETY = "health_safety"


class Jurisdiction(str, Enum):
    US_DELAWARE = "us_delaware"
    US_CALIFORNIA = "us_california"
    UK = "uk"
    US_FEDERAL = "us_federal"
    US_NEW_YORK = "us_new_york"


class SessionStage(str, Enum):
    INITIALIZATION = "initialization"
    BATCH_ANALYSIS = "batch_analysis"
    PLAN_REVIEW = "plan_review"
    DOCUMENT_CONVERSION = "document_conversion"
    SESSION_SUMMARY = "session_summary"
    COMPLETED = "completed"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    category: PolicyCategory
    source_jurisdiction: Jurisdiction
    stage: SessionStage = SessionStage.INITIALIZATION
    document_ids: list[str] = Field(default_factory=list)
    current_document_index: int = 0
    plan_approved: bool = False
    chat_history: list[dict] = Field(default_factory=list)
