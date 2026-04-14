from pydantic import BaseModel


class AgentDefinition(BaseModel):
    name: str
    display_name: str
    system_prompt: str
    tool_names: list[str]
    max_iterations: int


class OrchestratorResult(BaseModel):
    agent: str
    reasoning: str
