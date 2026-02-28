from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Structured Inventory System"
    app_version: str = "0.1.0"

    # Multimodal model config
    multimodal_provider: str = "mock"  # mock | volcengine

    # Volcano Engine (Ark) multimodal config
    volcengine_api_key: str = ""
    volcengine_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    volcengine_model: str = ""
    volcengine_timeout_seconds: int = 60

    # Feishu config
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_bitable_app_token: str = ""
    feishu_bitable_table_id: str = ""
    feishu_base_url: str = "https://open.feishu.cn"

    # Behavior flags
    default_skip_invalid_records: bool = True
    parse_max_concurrency: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
