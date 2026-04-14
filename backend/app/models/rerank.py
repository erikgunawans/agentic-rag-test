from pydantic import BaseModel


class RerankScore(BaseModel):
    index: int
    score: float  # 0.0 to 10.0


class RerankResponse(BaseModel):
    scores: list[RerankScore]
