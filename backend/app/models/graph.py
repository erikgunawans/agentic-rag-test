from pydantic import BaseModel


class ExtractedEntity(BaseModel):
    name: str
    entity_type: str
    canonical: str | None = None
    properties: dict = {}


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relationship: str
    properties: dict = {}


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]
