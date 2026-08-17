"""Application configuration.

No LLM API key is required to run this project: everything works fully
offline against the deterministic FixtureLLMClient. If ANTHROPIC_API_KEY or
OPENAI_API_KEY is present in the environment (or a .env file), the real
LLM-backed extractor is used instead. See llm/factory.py.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    openai_model: str = "gpt-4o-mini"

    db_path: str = str(REPO_ROOT / "doc_review.db")

    # Confidence-calibration thresholds for the three-state classifier.
    # Tuned in classifier.py; exposed here so they're easy to find/adjust
    # and so evaluation.py can sweep them.
    confidence_include_threshold: float = 0.72
    confidence_exclude_threshold: float = 0.30  # below this AND zero candidates => exclude path

    corpus_dir: str = str(REPO_ROOT / "fixtures" / "corpus")
    hand_labels_path: str = str(REPO_ROOT / "fixtures" / "hand_labels.json")


settings = Settings()
