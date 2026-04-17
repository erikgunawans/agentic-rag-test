from pydantic import BaseModel, Field
from typing import Literal


# ── LLM Response Model ────────────────────────────────────────

class BJREvidenceAssessment(BaseModel):
    satisfies_requirement: bool
    assessment: str
    gaps: list[str] = []
    regulatory_alignment: str = ""
    confidence_score: float = 0.0


# ── Request Models ────────────────────────────────────────────

class DecisionCreate(BaseModel):
    title: str
    description: str = ""
    decision_type: str = "other"
    risk_level: str | None = None
    estimated_value: float | None = None
    gcg_aspect_ids: list[str] = []
    metadata: dict = {}


class DecisionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    decision_type: str | None = None
    risk_level: str | None = None
    estimated_value: float | None = None
    gcg_aspect_ids: list[str] | None = None
    metadata: dict | None = None


class EvidenceCreate(BaseModel):
    checklist_item_id: str
    evidence_type: Literal["document", "tool_result", "manual_note", "approval", "external_link"]
    reference_id: str | None = None
    reference_table: str | None = None
    title: str
    notes: str | None = None
    external_url: str | None = None


class RiskCreate(BaseModel):
    decision_id: str | None = None
    risk_title: str
    description: str = ""
    risk_level: str = "medium"
    mitigation: str = ""
    owner_role: str = ""
    is_global: bool = False


class RiskUpdate(BaseModel):
    risk_title: str | None = None
    description: str | None = None
    risk_level: str | None = None
    mitigation: str | None = None
    status: str | None = None
    owner_role: str | None = None


class RegulatoryItemCreate(BaseModel):
    code: str
    title: str
    layer: Literal["uu", "pp", "pergub", "ojk_bei", "custom"]
    substance: str = ""
    url: str = ""
    critical_notes: str = ""


class RegulatoryItemUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    layer: str | None = None
    substance: str | None = None
    url: str | None = None
    critical_notes: str | None = None
    is_active: bool | None = None


class ChecklistTemplateCreate(BaseModel):
    phase: Literal["pre_decision", "decision", "post_decision"]
    item_order: int
    title: str
    description: str = ""
    regulatory_item_ids: list[str] = []
    is_required: bool = True


class ChecklistTemplateUpdate(BaseModel):
    item_order: int | None = None
    title: str | None = None
    description: str | None = None
    regulatory_item_ids: list[str] | None = None
    is_required: bool | None = None
    is_active: bool | None = None


class GCGAspectCreate(BaseModel):
    aspect_name: str
    regulatory_item_ids: list[str] = []
    indicators: list[str] = []
    frequency: str | None = None
    pic_role: str = ""


class GCGAspectUpdate(BaseModel):
    aspect_name: str | None = None
    regulatory_item_ids: list[str] | None = None
    indicators: list[str] | None = None
    frequency: str | None = None
    pic_role: str | None = None
    is_active: bool | None = None
