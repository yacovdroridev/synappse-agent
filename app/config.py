from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # WhatsApp Cloud API
    whatsapp_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v21.0"
    verify_token: str = "synappse-verify-token"

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    cheap_model: str = "gpt-4o-mini"
    strong_model: str = "gpt-4o"
    confidence_threshold: float = 0.6
    llm_provider: str = "auto"  # auto | mock | openai

    # App
    database_url: str = "sqlite:///./synappse.db"
    admin_token: str = "dev-admin-token"

    class Config:
        env_file = ".env"


settings = Settings()
