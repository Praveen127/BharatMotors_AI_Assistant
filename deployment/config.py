"""
config.py
Central runtime configuration, read from environment variables with safe
defaults. Never hard-codes secrets — see .env.example.
"""
import os


class Config:
    USE_MOCK_LLM = os.environ.get("USE_MOCK_LLM", "true").lower() == "true"
    # GOOGLE_API_KEY is the primary env var langchain-google-genai looks
    # for; GEMINI_API_KEY is accepted as a fallback by the SDK itself. See
    # https://ai.google.dev/gemini-api/docs/api-key for how to get one.
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
    # gemini-2.5-flash is GA and widely documented as of this writing, but
    # Google retires/replaces Gemini model names faster than most APIs --
    # check https://ai.google.dev/gemini-api/docs/models for the current
    # recommended model before relying on this default in production (a
    # deprecation notice for the 2.5 line was already issued for October
    # 2026; gemini-3-flash-preview / gemini-3.1-pro-preview are newer
    # options as of this writing but were still preview-stage).
    LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
    LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
    # text-embedding-004 is the long-stable Gemini embedding model; see
    # retrieval/embedder.py for the fallback used when this isn't available.
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "models/text-embedding-004")
    HOST = os.environ.get("APP_HOST", "0.0.0.0")
    # Most cloud platforms (Cloud Run, App Engine Flex, Render, Railway,
    # Heroku) inject a standard $PORT env var and expect the app to bind to
    # it; APP_PORT remains as a local-dev override, defaulting to 8080 to
    # match Cloud Run/App Engine's convention.
    PORT = int(os.environ.get("PORT", os.environ.get("APP_PORT", "8080")))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    MAX_REQUEST_CHARS = int(os.environ.get("MAX_REQUEST_CHARS", "2000"))
    REQUEST_TIMEOUT_S = float(os.environ.get("REQUEST_TIMEOUT_S", "15"))

    @classmethod
    def validate(cls):
        warnings = []
        if not cls.USE_MOCK_LLM and not cls.GOOGLE_API_KEY:
            warnings.append("USE_MOCK_LLM is false but GOOGLE_API_KEY is not set; "
                             "the agent will fall back to MockLLM at runtime.")
        return warnings
