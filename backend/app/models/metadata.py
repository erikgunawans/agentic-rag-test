from typing import Literal
from pydantic import BaseModel

VALID_CATEGORIES = ("technical", "legal", "business", "academic", "personal", "other")


class DocumentMetadata(BaseModel):
    title: str
    author: str | None = None
    date_period: str | None = None
    category: Literal["technical", "legal", "business", "academic", "personal", "other"] = "other"
    tags: list[str]
    summary: str
