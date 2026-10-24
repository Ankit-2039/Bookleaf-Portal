from app.ai.client import AIClient, mongo_usage_sink
from app.ai.provider import get_provider
from app.db import mongo


def get_ai_client() -> AIClient:
    """Provider + usage logging. Tests replace `get_provider` here so no test ever calls a real LLM."""
    return AIClient(get_provider(), mongo_usage_sink(mongo.get_db()))