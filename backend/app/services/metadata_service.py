import json
import logging
import tiktoken
from openai import AsyncOpenAI
from langsmith import traceable
from app.config import get_settings
from app.models.metadata import DocumentMetadata

logger = logging.getLogger(__name__)
settings = get_settings()

# Truncate to this many tokens before extraction (title pages / intros carry the metadata)
_MAX_EXTRACTION_TOKENS = 4000
_ENCODING = tiktoken.get_encoding("cl100k_base")

_SYSTEM_PROMPT = """You are a document metadata extractor. Extract structured metadata from the provided document text.

Return a JSON object with exactly these fields:
- title: The document's title, or a descriptive title based on the content (string, required)
- author: The author's name if identifiable, otherwise null
- date_period: Any date or time period referenced (e.g. "2024", "Q3 2023", "March 2025"), otherwise null
- category: One of exactly: technical, legal, business, academic, personal, other
- tags: 3 to 7 descriptive keyword tags as a JSON array of strings
- summary: A 2 to 3 sentence summary of the document (string, required)

Return only the JSON object, no other text."""


def _truncate(text: str) -> str:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= _MAX_EXTRACTION_TOKENS:
        return text
    return _ENCODING.decode(tokens[:_MAX_EXTRACTION_TOKENS])


class MetadataService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = settings.openrouter_model

    @traceable(name="extract_document_metadata")
    async def extract_metadata(self, text: str, model: str | None = None) -> DocumentMetadata | None:
        truncated = _truncate(text)
        try:
            response = await self.client.chat.completions.create(
                model=model or self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Document text:\n\n{truncated}"},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = response.choices[0].message.content or ""
            return DocumentMetadata.model_validate_json(raw)
        except Exception as e:
            logger.warning("Metadata extraction failed: %s", e)
            return None
