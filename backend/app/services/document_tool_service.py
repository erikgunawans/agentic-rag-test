import json
import logging
from pydantic import BaseModel
from langsmith import traceable
from app.config import get_settings
from app.services.openrouter_service import OpenRouterService
from app.services.ingestion_service import parse_text

logger = logging.getLogger(__name__)
settings = get_settings()
openrouter = OpenRouterService()


# ── Pydantic response models ──────────────────────────────────────────

class GeneratedDocument(BaseModel):
    title: str
    content: str
    summary: str


class ComparisonDifference(BaseModel):
    section: str
    doc_a: str
    doc_b: str
    significance: str  # "high" | "medium" | "low"


class ComparisonResult(BaseModel):
    summary: str
    differences: list[ComparisonDifference]
    risk_assessment: str
    recommendation: str


class ComplianceFinding(BaseModel):
    category: str
    status: str  # "pass" | "review" | "fail"
    description: str
    recommendation: str


class ComplianceResult(BaseModel):
    overall_status: str  # "pass" | "review" | "fail"
    summary: str
    findings: list[ComplianceFinding]
    missing_provisions: list[str]


class AnalysisRisk(BaseModel):
    clause: str
    risk_level: str  # "high" | "medium" | "low"
    description: str
    recommendation: str


class AnalysisObligation(BaseModel):
    party: str
    obligation: str
    deadline: str | None = None


class AnalysisResult(BaseModel):
    overall_risk: str  # "high" | "medium" | "low"
    summary: str
    risks: list[AnalysisRisk]
    obligations: list[AnalysisObligation]
    critical_clauses: list[str]
    missing_provisions: list[str]


# ── Helper ─────────────────────────────────────────────────────────────

def _extract_text(file_bytes: bytes, mime_type: str) -> str:
    text = parse_text(file_bytes, mime_type)
    # Truncate to ~12k tokens (~48k chars) to stay within LLM context
    max_chars = 48_000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Document truncated due to length]"
    return text


async def _llm_json(system_prompt: str, user_prompt: str) -> dict:
    """Call OpenRouter and parse the JSON response."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    result = await openrouter.complete_with_tools(
        messages=messages,
        response_format={"type": "json_object"},
    )
    return json.loads(result["content"])


# ── Document Creation ──────────────────────────────────────────────────

@traceable(name="document_creation")
async def create_document(
    doc_type: str,
    fields: dict,
    output_language: str,
    reference_text: str | None = None,
    template_text: str | None = None,
) -> GeneratedDocument:
    lang_instruction = (
        "Write the document in both English and Indonesian (bilingual, side by side sections)."
        if output_language == "both"
        else "Write the document entirely in Indonesian (Bahasa Indonesia)."
    )

    system_prompt = f"""You are a professional legal document drafting assistant specializing in Indonesian and international law.
Generate a complete, professional {doc_type} document based on the provided parameters.
{lang_instruction}
Return JSON with keys: title, content, summary.
- title: A professional document title
- content: The full document text with proper legal formatting, numbered sections, and clauses
- summary: A 1-2 sentence summary of the document"""

    user_parts = [f"Document Type: {doc_type}", "Parameters:"]
    for key, value in fields.items():
        if value:
            user_parts.append(f"  {key}: {value}")

    if reference_text:
        user_parts.append(f"\nReference Document:\n{reference_text[:20000]}")
    if template_text:
        user_parts.append(f"\nTemplate Document:\n{template_text[:20000]}")

    data = await _llm_json(system_prompt, "\n".join(user_parts))
    return GeneratedDocument(**data)


# ── Document Comparison ────────────────────────────────────────────────

@traceable(name="document_comparison")
async def compare_documents(
    doc_a_text: str,
    doc_b_text: str,
    focus: str,
    context: str | None = None,
) -> ComparisonResult:
    focus_map = {
        "full": "Compare the entire documents thoroughly, section by section.",
        "clauses": "Focus specifically on comparing the main legal clauses and their implications.",
        "risks": "Focus on identifying risk differences between the two documents.",
    }

    system_prompt = f"""You are a legal document comparison specialist.
{focus_map.get(focus, focus_map["full"])}
Return JSON with keys: summary, differences, risk_assessment, recommendation.
- summary: Overview of the comparison (2-3 sentences)
- differences: Array of objects with section, doc_a (text from doc A), doc_b (text from doc B), significance ("high"/"medium"/"low")
- risk_assessment: Overall risk implications of the differences
- recommendation: Actionable recommendation"""

    user_prompt = f"Document A:\n{doc_a_text}\n\n---\n\nDocument B:\n{doc_b_text}"
    if context:
        user_prompt += f"\n\nAdditional Context: {context}"

    data = await _llm_json(system_prompt, user_prompt)
    return ComparisonResult(**data)


# ── Compliance Check ───────────────────────────────────────────────────

@traceable(name="compliance_check")
async def check_compliance(
    doc_text: str,
    framework: str,
    scopes: list[str],
    context: str | None = None,
) -> ComplianceResult:
    framework_map = {
        "ojk": "OJK (Otoritas Jasa Keuangan / Indonesian Financial Services Authority) regulations",
        "international": "International legal standards and best practices",
        "gdpr": "EU General Data Protection Regulation (GDPR)",
        "custom": "General legal compliance best practices",
    }
    scope_map = {
        "legal": "Legal clause compliance",
        "risks": "Risk flags and potential liabilities",
        "missing": "Missing provisions that should be present",
        "regulatory": "Regulatory compliance requirements",
    }

    scope_instructions = ", ".join(scope_map.get(s, s) for s in scopes)

    system_prompt = f"""You are a regulatory compliance expert specializing in {framework_map.get(framework, framework)}.
Check the document against the specified framework, focusing on: {scope_instructions}.
Return JSON with keys: overall_status, summary, findings, missing_provisions.
- overall_status: "pass", "review", or "fail"
- summary: 2-3 sentence overview of compliance status
- findings: Array of objects with category, status ("pass"/"review"/"fail"), description, recommendation
- missing_provisions: Array of strings listing provisions that should be present but are missing"""

    user_prompt = f"Document:\n{doc_text}"
    if context:
        user_prompt += f"\n\nAdditional Context: {context}"

    data = await _llm_json(system_prompt, user_prompt)
    return ComplianceResult(**data)


# ── Contract Analysis ──────────────────────────────────────────────────

@traceable(name="contract_analysis")
async def analyze_contract(
    doc_text: str,
    analysis_types: list[str],
    law: str,
    depth: str,
    context: str | None = None,
) -> AnalysisResult:
    law_map = {
        "indonesia": "Indonesian law (Hukum Indonesia)",
        "singapore": "Singapore law",
        "international": "International law and conventions",
        "custom": "General legal principles",
    }
    type_map = {
        "risk": "Risk Assessment",
        "obligations": "Key Obligations extraction",
        "clauses": "Critical Clauses identification",
        "missing": "Missing Provisions detection",
    }
    depth_map = {
        "quick": "Provide a quick high-level scan. Be concise.",
        "standard": "Provide a standard analysis with moderate detail.",
        "deep": "Provide a comprehensive deep-dive analysis. Be thorough and detailed.",
    }

    type_instructions = ", ".join(type_map.get(t, t) for t in analysis_types)

    system_prompt = f"""You are a contract analysis specialist with expertise in {law_map.get(law, law)}.
Analyze the contract focusing on: {type_instructions}.
{depth_map.get(depth, depth_map["standard"])}
Return JSON with keys: overall_risk, summary, risks, obligations, critical_clauses, missing_provisions.
- overall_risk: "high", "medium", or "low"
- summary: 2-3 sentence overview of the contract analysis
- risks: Array of objects with clause, risk_level ("high"/"medium"/"low"), description, recommendation
- obligations: Array of objects with party, obligation, deadline (string or null)
- critical_clauses: Array of strings listing critical clauses found
- missing_provisions: Array of strings listing missing provisions"""

    user_prompt = f"Contract:\n{doc_text}"
    if context:
        user_prompt += f"\n\nAdditional Context: {context}"

    data = await _llm_json(system_prompt, user_prompt)
    return AnalysisResult(**data)
