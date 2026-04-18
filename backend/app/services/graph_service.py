import json
import logging
import re
from langsmith import traceable
from app.config import get_settings
from app.database import get_supabase_client
from app.services.openrouter_service import OpenRouterService
from app.models.graph import ExtractionResult

logger = logging.getLogger(__name__)
settings = get_settings()
openrouter = OpenRouterService()

_EXTRACTION_SYSTEM_PROMPT = """You are an Indonesian legal entity extractor. Given document chunks, extract:

1. ENTITIES — named objects of these types:
   - regulation: Indonesian laws/regulations (UU, PP, Perpres, Permen, POJK, SE-OJK, Perda).
     Include the full identifier: type, number, year, and short title if present.
   - company: Companies, organizations (PT, CV, Yayasan, Koperasi, etc.)
   - person: Named individuals
   - institution: Government bodies, agencies (OJK, BI, Kemenkumham, BEI, etc.)

2. RELATIONSHIPS between entities:
   - references: entity A cites/references entity B
   - amends: regulation A amends/modifies regulation B
   - obligates: regulation/clause obliges a party
   - signed_by: document/contract signed by person/company
   - governs: regulation governs a party/activity

For each entity, provide a canonical form:
- Regulations: lowercase type_number_year (e.g., "uu_11_2020")
- Companies: lowercase underscored (e.g., "pt_bank_negara_indonesia")
- Persons: lowercase underscored (e.g., "budi_santoso")

Return JSON: {"entities": [...], "relationships": [...]}
entities: [{name, entity_type, canonical, properties}]
relationships: [{source, target, relationship, properties}]

Only extract entities that are explicitly named. Do not infer."""

_CHUNK_BATCH_SIZE = 5
_MAX_GRAPH_CONTEXT_CHARS = 2000


class GraphService:

    @traceable(name="extract_entities_from_chunks")
    async def extract_entities(
        self,
        chunks: list[str],
        doc_metadata: dict | None = None,
        model: str | None = None,
    ) -> ExtractionResult:
        """Extract entities and relationships from document chunks using LLM."""
        all_entities = []
        all_relationships = []

        doc_hint = ""
        if doc_metadata:
            parts = []
            if doc_metadata.get("title"):
                parts.append(f"Document: {doc_metadata['title']}")
            if doc_metadata.get("category"):
                parts.append(f"Category: {doc_metadata['category']}")
            if parts:
                doc_hint = " | ".join(parts) + "\n\n"

        for i in range(0, len(chunks), _CHUNK_BATCH_SIZE):
            batch = chunks[i : i + _CHUNK_BATCH_SIZE]
            user_prompt = doc_hint + "\n\n---\n\n".join(
                f"[Chunk {i + j + 1}]\n{chunk}" for j, chunk in enumerate(batch)
            )

            try:
                result = await openrouter.complete(
                    model=model or settings.openrouter_model,
                    messages=[
                        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                )
                raw = result.choices[0].message.content or "{}"
                parsed = json.loads(raw)
                batch_result = ExtractionResult.model_validate(parsed)
                all_entities.extend(batch_result.entities)
                all_relationships.extend(batch_result.relationships)
            except Exception as e:
                logger.warning("Entity extraction failed for batch %d: %s", i, e)

        # Deduplicate entities by canonical form
        seen = {}
        deduped = []
        for entity in all_entities:
            canonical = entity.canonical or self._canonicalize(entity.name, entity.entity_type)
            entity.canonical = canonical
            if canonical not in seen:
                seen[canonical] = entity
                deduped.append(entity)

        return ExtractionResult(entities=deduped, relationships=all_relationships)

    def _canonicalize(self, name: str, entity_type: str) -> str:
        """Normalize entity name for deduplication."""
        if entity_type == "regulation":
            match = re.search(
                r"(UU|PP|Perpres|Permen|POJK|SE-OJK|Perda)\s*(?:No\.?\s*)?(\d+).*?(\d{4})",
                name,
                re.IGNORECASE,
            )
            if match:
                return f"{match.group(1).lower()}_{match.group(2)}_{match.group(3)}"
        return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

    @traceable(name="store_graph_entities")
    async def store_entities(
        self,
        extraction: ExtractionResult,
        doc_id: str,
        user_id: str,
        chunk_ids: list[str],
        chunks: list[str],
    ) -> None:
        """Upsert entities, create relationships, link entities to chunks."""
        client = get_supabase_client()
        entity_id_map: dict[str, str] = {}  # canonical -> entity uuid

        # Upsert entities
        for entity in extraction.entities:
            canonical = entity.canonical or self._canonicalize(entity.name, entity.entity_type)
            try:
                result = client.table("graph_entities").upsert(
                    {
                        "user_id": user_id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "canonical": canonical,
                        "properties": entity.properties,
                    },
                    on_conflict="user_id,entity_type,canonical",
                ).execute()
                if result.data:
                    entity_id_map[canonical] = result.data[0]["id"]
            except Exception as e:
                logger.warning("Failed to upsert entity %s: %s", entity.name, e)

        # Re-fetch entities that existed already (upsert may not return id on conflict)
        if extraction.entities:
            canonicals = [
                e.canonical or self._canonicalize(e.name, e.entity_type)
                for e in extraction.entities
            ]
            existing = client.table("graph_entities") \
                .select("id, canonical") \
                .eq("user_id", user_id) \
                .in_("canonical", canonicals) \
                .execute()
            for row in existing.data or []:
                entity_id_map[row["canonical"]] = row["id"]

        # Create relationships
        for rel in extraction.relationships:
            source_canonical = self._canonicalize(rel.source, "")
            target_canonical = self._canonicalize(rel.target, "")
            # Find entity IDs by matching canonical prefix
            source_id = self._find_entity_id(source_canonical, entity_id_map)
            target_id = self._find_entity_id(target_canonical, entity_id_map)
            if source_id and target_id and source_id != target_id:
                try:
                    client.table("graph_relationships").insert({
                        "user_id": user_id,
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship": rel.relationship,
                        "properties": rel.properties,
                        "document_id": doc_id,
                    }).execute()
                except Exception as e:
                    logger.warning("Failed to create relationship %s->%s: %s", rel.source, rel.target, e)

        # Link entities to chunks where they appear
        for canonical, entity_id in entity_id_map.items():
            entity_name = next(
                (e.name for e in extraction.entities
                 if (e.canonical or self._canonicalize(e.name, e.entity_type)) == canonical),
                "",
            )
            if not entity_name:
                continue
            name_lower = entity_name.lower()
            for idx, chunk in enumerate(chunks):
                if name_lower in chunk.lower() and idx < len(chunk_ids):
                    try:
                        client.table("graph_entity_chunks").insert({
                            "entity_id": entity_id,
                            "chunk_id": chunk_ids[idx],
                            "document_id": doc_id,
                            "user_id": user_id,
                        }).execute()
                    except Exception:
                        pass  # duplicate or FK constraint — skip silently

    def _find_entity_id(self, canonical: str, entity_id_map: dict[str, str]) -> str | None:
        """Find entity ID by canonical, with fuzzy prefix matching."""
        if canonical in entity_id_map:
            return entity_id_map[canonical]
        # Try partial match (e.g., relationship source is just "PT Maju" not full canonical)
        for key, eid in entity_id_map.items():
            if canonical in key or key in canonical:
                return eid
        return None

    @traceable(name="get_graph_context")
    async def get_graph_context(
        self,
        chunk_ids: list[str],
        user_id: str,
        max_hops: int = 1,
    ) -> dict:
        """Fetch graph context for retrieved chunks via SQL RPC."""
        try:
            client = get_supabase_client()
            result = client.rpc(
                "get_graph_context_for_chunks",
                {
                    "p_chunk_ids": chunk_ids,
                    "p_user_id": user_id,
                    "p_max_hops": max_hops,
                },
            ).execute()
            return result.data or {}
        except Exception as e:
            logger.warning("Graph context RPC failed: %s", e)
            return {}

    def format_graph_context(self, graph_data: dict) -> str:
        """Format graph context as human-readable text for LLM injection."""
        lines = []
        entities = graph_data.get("entities") or []
        relationships = graph_data.get("relationships") or []
        neighbors = graph_data.get("neighbor_entities") or []
        cross_chunks = graph_data.get("cross_document_chunks") or []

        if entities:
            lines.append("--- Related Entities ---")
            entity_map = {e["id"]: e for e in entities + neighbors}
            for entity in entities:
                lines.append(f"[{entity['entity_type']}] {entity['name']}")

            if relationships:
                for rel in relationships:
                    src = entity_map.get(rel["source_id"], {}).get("name", "?")
                    tgt = entity_map.get(rel["target_id"], {}).get("name", "?")
                    lines.append(f"  {src} --{rel['relationship']}--> {tgt}")

        if cross_chunks:
            lines.append("")
            lines.append("--- Cross-Document Connections ---")
            for cc in cross_chunks[:5]:
                filename = cc.get("filename", "unknown")
                content = (cc.get("content") or "")[:200]
                lines.append(f"  [{filename}]: {content}...")

        result = "\n".join(lines)
        if len(result) > _MAX_GRAPH_CONTEXT_CHARS:
            result = result[:_MAX_GRAPH_CONTEXT_CHARS] + "\n[truncated]"
        return result
