from app.core.config import get_settings
from app.modules.ai.provider import AIProvider
from app.modules.ai.stub_provider import StubAIProvider


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    # Future: branch on settings.ai_provider (openai, etc.)
    _ = settings.ai_provider
    return StubAIProvider()
