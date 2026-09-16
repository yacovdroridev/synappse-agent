from ..config import settings


def get_provider():
    """auto -> mock when no API key, so dev/demo/tests need zero credentials."""
    if settings.llm_provider == "mock":
        from .mock import MockProvider
        return MockProvider()
    if settings.llm_provider == "openai" or (settings.llm_provider == "auto" and settings.openai_api_key):
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    from .mock import MockProvider
    return MockProvider()
