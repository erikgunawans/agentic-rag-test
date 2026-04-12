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

class ClauseRisk(BaseModel):
    clause_title: str
    risk_level: str
    risk_note: str


class GeneratedDocument(BaseModel):
    title: str
    content: str
    summary: str
    confidence_score: float = 0.0
    clause_risks: list[dict] = []


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
    confidence_score: float = 0.0


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
    confidence_score: float = 0.0


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
    confidence_score: float = 0.0


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
    clauses: list[dict] | None = None,
) -> GeneratedDocument:
    lang_instruction = (
        "Write the document in both English and Indonesian (bilingual, side by side sections)."
        if output_language == "both"
        else "Write the document entirely in Indonesian (Bahasa Indonesia)."
    )

    clause_instruction = ""
    if clauses:
        clause_instruction = """
If clauses are provided below, incorporate them into the document in their designated sections.
For each clause, assess its risk in the context of this specific document and return a per-clause risk assessment.
Return JSON with keys: title, content, summary, confidence_score, clause_risks.
- clause_risks: (array of objects) Each object has: clause_title (string), risk_level ("high"/"medium"/"low"), risk_note (string, 1 sentence explaining the contextual risk)"""
    else:
        clause_instruction = """
Return JSON with keys: title, content, summary, confidence_score, clause_risks.
- clause_risks: (array) Return an empty array []"""

    system_prompt = f"""You are a professional legal document drafting assistant specializing in Indonesian and international law.
Generate a complete, professional {doc_type} document based on the provided parameters.
{lang_instruction}
{clause_instruction}
- title: (string) A professional document title
- content: (string) The full document text as a single string with proper legal formatting, numbered sections, and clauses. If bilingual, include both languages in one string separated by section headers.
- summary: (string) A 1-2 sentence summary of the document
- confidence_score: (float 0.0-1.0) Your confidence in the quality and legal soundness of this document. 1.0 = fully confident; lower = uncertainty about correctness or completeness."""

    user_parts = [f"Document Type: {doc_type}", "Parameters:"]
    for key, value in fields.items():
        if value:
            user_parts.append(f"  {key}: {value}")

    if reference_text:
        user_parts.append(f"\nReference Document:\n{reference_text[:20000]}")
    if template_text:
        user_parts.append(f"\nTemplate Document:\n{template_text[:20000]}")

    if clauses:
        total_chars = 0
        user_parts.append("\nInclude these clauses in the document:")
        for i, c in enumerate(clauses, 1):
            clause_content = c["content"][:2000]
            total_chars += len(clause_content)
            if total_chars > 20000:
                user_parts.append(f"\n(Remaining clauses truncated due to length)")
                break
            user_parts.append(f"  Clause {i} — {c['title']} (baseline risk: {c['risk_level']}):\n    {clause_content}")

    data = await _llm_json(system_prompt, "\n".join(user_parts))
    # Handle case where LLM returns content as dict (e.g. {"English": "...", "Indonesian": "..."})
    if isinstance(data.get("content"), dict):
        parts = [f"--- {lang} ---\n{text}" for lang, text in data["content"].items()]
        data["content"] = "\n\n".join(parts)
    # Ensure clause_risks defaults to empty list
    if "clause_risks" not in data:
        data["clause_risks"] = []
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
Return JSON with keys: summary, differences, risk_assessment, recommendation, confidence_score.
- summary: Overview of the comparison (2-3 sentences)
- differences: Array of objects with section, doc_a (text from doc A), doc_b (text from doc B), significance ("high"/"medium"/"low")
- risk_assessment: Overall risk implications of the differences
- recommendation: Actionable recommendation
- confidence_score: (float 0.0-1.0) Your confidence in the accuracy and completeness of this comparison. 1.0 = fully confident all differences are correctly identified."""

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
Return JSON with keys: overall_status, summary, findings, missing_provisions, confidence_score.
- overall_status: "pass", "review", or "fail"
- summary: 2-3 sentence overview of compliance status
- findings: Array of objects with category, status ("pass"/"review"/"fail"), description, recommendation
- missing_provisions: Array of strings listing provisions that should be present but are missing
- confidence_score: (float 0.0-1.0) Your confidence in the accuracy of this compliance assessment. 1.0 = fully confident the assessment is correct against the specified framework."""

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
Return JSON with keys: overall_risk, summary, risks, obligations, critical_clauses, missing_provisions, confidence_score.
- overall_risk: "high", "medium", or "low"
- summary: 2-3 sentence overview of the contract analysis
- risks: Array of objects with clause, risk_level ("high"/"medium"/"low"), description, recommendation
- obligations: Array of objects with party, obligation, deadline (string or null)
- critical_clauses: Array of strings listing critical clauses found
- missing_provisions: Array of strings listing missing provisions
- confidence_score: (float 0.0-1.0) Your confidence in the accuracy and completeness of this analysis. 1.0 = fully confident all risks, obligations, and clauses are correctly identified."""

    user_prompt = f"Contract:\n{doc_text}"
    if context:
        user_prompt += f"\n\nAdditional Context: {context}"

    data = await _llm_json(system_prompt, user_prompt)
    return AnalysisResult(**data)
