import os
from app.config import get_settings


def configure_langsmith() -> None:
    settings = get_settings()
    if not settings.langsmith_api_key:
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    print(f"LangSmith tracing enabled — project: {settings.langsmith_project}")
