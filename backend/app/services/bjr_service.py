import json
import logging
from app.services.tracing_service import traced
from app.config import get_settings
from app.services.openrouter_service import OpenRouterService
from app.services.system_settings_service import get_system_settings
from app.database import get_supabase_client
from app.models.bjr import BJREvidenceAssessment

logger = logging.getLogger(__name__)
settings = get_settings()
openrouter = OpenRouterService()

PHASE_ORDER = ["pre_decision", "decision", "post_decision", "completed"]


async def _llm_json(system_prompt: str, user_prompt: str) -> dict:
    """Call OpenRouter with JSON response format."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = await openrouter.complete_with_tools(
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(result["content"])


@traced(name="bjr_evidence_assessment")
async def assess_evidence(
    evidence_text: str,
    checklist_item_title: str,
    checklist_item_description: str,
    regulatory_references: list[str],
    decision_context: str,
) -> BJREvidenceAssessment:
    """Assess whether evidence satisfies a specific BJR checklist requirement."""
    reg_list = "\n".join(f"- {r}" for r in regulatory_references) if regulatory_references else "Tidak ada referensi spesifik."

    system_prompt = """Anda adalah pakar hukum korporasi Indonesia yang mengkhususkan diri pada Business Judgment Rule (BJR) dan Good Corporate Governance (GCG) untuk BUMD.

Tugas Anda: Menilai apakah dokumen bukti yang diberikan memenuhi persyaratan checklist BJR tertentu.

Evaluasi berdasarkan:
1. Apakah bukti secara substansial memenuhi persyaratan checklist
2. Kesesuaian dengan regulasi yang dirujuk
3. Kelengkapan — apakah ada aspek yang kurang atau lemah
4. Kecukupan untuk pembuktian di hadapan auditor atau aparat hukum

Respond in JSON with keys:
- satisfies_requirement (boolean): true if the evidence substantially meets the requirement
- assessment (string): 2-3 sentence evaluation in Indonesian
- gaps (array of strings): specific missing elements or weaknesses, empty array if none
- regulatory_alignment (string): how this evidence aligns with cited regulations
- confidence_score (float 0.0-1.0): your confidence in this assessment"""

    user_prompt = f"""Persyaratan Checklist BJR:
Judul: {checklist_item_title}
Deskripsi: {checklist_item_description}

Regulasi yang Dirujuk:
{reg_list}

Konteks Keputusan:
{decision_context}

Dokumen Bukti:
{evidence_text[:24000]}"""

    try:
        data = await _llm_json(system_prompt, user_prompt)
        return BJREvidenceAssessment(**data)
    except Exception as e:
        logger.error(f"BJR evidence assessment failed: {e}")
        return BJREvidenceAssessment(
            satisfies_requirement=False,
            assessment=f"Penilaian otomatis gagal: {str(e)}",
            gaps=["Penilaian LLM tidak tersedia"],
            regulatory_alignment="",
            confidence_score=0.0,
        )


def calculate_bjr_score(decision_id: str) -> float:
    """Calculate overall BJR completeness score (0-100) for a decision."""
    client = get_supabase_client()

    decision = client.table("bjr_decisions").select("current_phase").eq("id", decision_id).execute()
    if not decision.data:
        return 0.0

    current_phase = decision.data[0]["current_phase"]

    # Get all required checklist items for completed + current phases
    phases_to_check = []
    for p in PHASE_ORDER:
        phases_to_check.append(p)
        if p == current_phase:
            break
    # Remove 'completed' from phases since it's not an actual checklist phase
    phases_to_check = [p for p in phases_to_check if p != "completed"]

    if not phases_to_check:
        return 100.0 if current_phase == "completed" else 0.0

    items = client.table("bjr_checklist_templates").select("id, phase, is_required").eq("is_active", True).in_("phase", phases_to_check).execute()
    required_items = [i for i in items.data if i["is_required"]]

    if not required_items:
        return 100.0

    # Get evidence with approved/auto_approved status for these items
    item_ids = [i["id"] for i in required_items]
    evidence = client.table("bjr_evidence").select("checklist_item_id, review_status").eq("decision_id", decision_id).in_("checklist_item_id", item_ids).in_("review_status", ["auto_approved", "approved"]).execute()

    satisfied_ids = set(e["checklist_item_id"] for e in evidence.data)
    score = (len(satisfied_ids) / len(required_items)) * 100.0
    return round(score, 1)


def bjr_advance_phase(decision_id: str) -> str | None:
    """Advance a decision to the next phase. Returns new phase or None if already completed."""
    client = get_supabase_client()

    decision = client.table("bjr_decisions").select("current_phase, status").eq("id", decision_id).execute()
    if not decision.data:
        return None

    current = decision.data[0]["current_phase"]
    idx = PHASE_ORDER.index(current) if current in PHASE_ORDER else -1

    if idx < 0 or idx >= len(PHASE_ORDER) - 1:
        return None

    next_phase = PHASE_ORDER[idx + 1]
    update_data = {
        "current_phase": next_phase,
        "status": "in_progress" if next_phase != "completed" else "completed",
    }
    if next_phase == "completed":
        update_data["completed_at"] = "now()"

    # Recalculate score
    update_data["bjr_score"] = calculate_bjr_score(decision_id)

    client.table("bjr_decisions").update(update_data).eq("id", decision_id).execute()
    return next_phase
