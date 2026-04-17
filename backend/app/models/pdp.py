from pydantic import BaseModel
from typing import Literal


# ── LLM Response Model ────────────────────────────────────────

class PersonalDataFinding(BaseModel):
    category: str
    confidence: float
    excerpt: str
    context: str = ""


class PersonalDataScanResult(BaseModel):
    data_categories_found: list[str] = []
    findings: list[PersonalDataFinding] = []
    suggested_lawful_basis: str = "contract"
    suggested_retention: str = ""
    confidence_score: float = 0.0


# ── Request Models ────────────────────────────────────────────

LAWFUL_BASES = Literal["consent", "contract", "legal_obligation", "vital_interest", "public_task", "legitimate_interest"]
DPIA_STATUSES = Literal["not_started", "in_progress", "completed"]
INCIDENT_TYPES = Literal["unauthorized_access", "ransomware", "accidental_disclosure", "data_loss", "insider_threat"]
RESPONSE_STATUSES = Literal["reported", "investigating", "remediated", "closed"]


class InventoryCreate(BaseModel):
    processing_activity: str
    data_categories: list[str] = []
    lawful_basis: LAWFUL_BASES = "contract"
    purposes: list[str] = []
    data_subjects: list[str] = []
    processors: list[dict] = []
    retention_period: str | None = None
    security_measures: list[str] = []
    dpia_required: bool = False
    dpia_status: DPIA_STATUSES = "not_started"


class InventoryUpdate(BaseModel):
    processing_activity: str | None = None
    data_categories: list[str] | None = None
    lawful_basis: LAWFUL_BASES | None = None
    purposes: list[str] | None = None
    data_subjects: list[str] | None = None
    processors: list[dict] | None = None
    retention_period: str | None = None
    security_measures: list[str] | None = None
    dpia_required: bool | None = None
    dpia_status: DPIA_STATUSES | None = None
    status: Literal["active", "archived"] | None = None


class ComplianceStatusUpdate(BaseModel):
    dpo_appointed: bool | None = None
    dpo_name: str | None = None
    dpo_email: str | None = None
    breach_plan_exists: bool | None = None


class IncidentCreate(BaseModel):
    incident_date: str
    incident_type: INCIDENT_TYPES
    description: str = ""
    affected_data_categories: list[str] = []
    estimated_records: int | None = None


class IncidentUpdate(BaseModel):
    response_status: RESPONSE_STATUSES | None = None
    root_cause: str | None = None
    remediation_actions: str | None = None
    regulator_notified_at: str | None = None
    subjects_notified_at: str | None = None
