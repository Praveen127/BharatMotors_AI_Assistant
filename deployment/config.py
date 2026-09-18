"""
config.py
Central runtime configuration, read from environment variables with safe
defaults. Never hard-codes secrets — see .env.example.
"""
import os


class Config:
    USE_MOCK_LLM = os.environ.get("USE_MOCK_LLM", "true").lower() == "true"
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
    HOST = os.environ.get("APP_HOST", "0.0.0.0")
    PORT = int(os.environ.get("APP_PORT", "8000"))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    MAX_REQUEST_CHARS = int(os.environ.get("MAX_REQUEST_CHARS", "2000"))
    REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "15"))

    @classmethod
    def validate(cls):
        warnings = []
        if not cls.USE_MOCK_LLM and not cls.OPENAI_API_KEY:
            warnings.append("USE_MOCK_LLM is false but OPENAI_API_KEY is not set; "
                             "the agent will fall back to MockLLM at runtime.")
        return warnings
