from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool = True
    smtp_from_email: str

    api_key: str
    rate_limit: str = "20/minute"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]
