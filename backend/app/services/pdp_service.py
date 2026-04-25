import json
import logging
from app.services.tracing_service import traced
from app.services.openrouter_service import OpenRouterService
from app.database import get_supabase_client
from app.models.pdp import PersonalDataScanResult

logger = logging.getLogger(__name__)
openrouter = OpenRouterService()


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


@traced(name="personal_data_scan")
async def scan_for_personal_data(doc_text: str) -> PersonalDataScanResult:
    """Scan a document for personal data categories per UU PDP."""
    system_prompt = """Anda adalah pakar privasi data Indonesia yang mengkhususkan diri pada UU PDP No. 27/2022.

Tugas Anda: Mengidentifikasi semua data pribadi dalam dokumen yang diberikan.

Kategori data pribadi yang harus dideteksi:
- nama (nama lengkap, nama panggilan)
- nik (Nomor Induk Kependudukan / NIK)
- email (alamat email)
- telepon (nomor telepon / HP)
- alamat (alamat fisik)
- rekening_bank (nomor rekening, nama bank)
- paspor (nomor paspor)
- ktp (data KTP)
- biometrik (sidik jari, wajah, retina)
- kesehatan (data medis / kesehatan)
- keuangan (data keuangan pribadi)
- agama (data keagamaan)
- ras_etnis (data ras/etnis)
- orientasi_seksual
- pandangan_politik
- data_anak (data anak di bawah umur)

Untuk setiap temuan, berikan:
- category: kategori data (dari daftar di atas)
- confidence: 0.0-1.0 seberapa yakin ini adalah data pribadi
- excerpt: kutipan teks yang mengandung data pribadi (maks 100 karakter)
- context: penjelasan singkat mengapa ini termasuk data pribadi

Juga rekomendasikan:
- suggested_lawful_basis: dasar hukum pemrosesan yang paling sesuai
- suggested_retention: periode retensi yang disarankan
- confidence_score: kepercayaan keseluruhan pada hasil pemindaian

Respond in JSON with keys: data_categories_found, findings, suggested_lawful_basis, suggested_retention, confidence_score"""

    user_prompt = f"Dokumen untuk dipindai:\n\n{doc_text[:24000]}"

    try:
        data = await _llm_json(system_prompt, user_prompt)
        return PersonalDataScanResult(**data)
    except Exception as e:
        logger.error(f"Personal data scan failed: {e}")
        return PersonalDataScanResult(
            data_categories_found=[],
            findings=[],
            confidence_score=0.0,
        )


def calculate_readiness_score() -> float:
    """Calculate UU PDP compliance readiness score (0-100)."""
    client = get_supabase_client()

    # Get compliance status
    status = client.table("pdp_compliance_status").select("*").eq("id", 1).execute()
    if not status.data:
        return 0.0
    s = status.data[0]

    score = 0.0

    # DPO appointed (20 points)
    if s.get("dpo_appointed"):
        score += 20.0

    # Breach plan exists (20 points)
    if s.get("breach_plan_exists"):
        score += 20.0

    # Data inventory completeness (30 points)
    inventory = client.table("data_inventory").select("id, dpia_required, dpia_status", count="exact").eq("status", "active").execute()
    inv_count = inventory.count if inventory.count is not None else len(inventory.data)
    if inv_count > 0:
        # At least 1 inventory item = 15 points, scale up to 30 for 10+ items
        score += min(30.0, 15.0 + (inv_count - 1) * 1.5)

    # DPIA coverage (30 points)
    if inventory.data:
        dpia_required = [i for i in inventory.data if i.get("dpia_required")]
        if dpia_required:
            dpia_completed = sum(1 for i in dpia_required if i.get("dpia_status") == "completed")
            score += (dpia_completed / len(dpia_required)) * 30.0
        else:
            score += 30.0  # No DPIA required = full marks

    return round(min(100.0, score), 1)
