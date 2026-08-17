"""Picks the LLMClient backend: real if a key is configured, deterministic
fixture backend otherwise. This is the one place that decides which
backend runs -- everything downstream (extraction.py, classifier.py) is
identical either way.
"""
from doc_review.config import settings
from doc_review.llm.base import LLMClient
from doc_review.llm.fixture import FixtureLLMClient


def get_default_llm_client() -> LLMClient:
    if settings.anthropic_api_key:
        from doc_review.llm.real import AnthropicLLMClient

        return AnthropicLLMClient(settings.anthropic_api_key, settings.anthropic_model)
    if settings.openai_api_key:
        from doc_review.llm.real import OpenAILLMClient

        return OpenAILLMClient(settings.openai_api_key, settings.openai_model)
    return FixtureLLMClient()
