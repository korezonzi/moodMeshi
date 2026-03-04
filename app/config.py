from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    ANTHROPIC_API_KEY: str
    RAKUTEN_APP_ID: str
    RAKUTEN_ACCESS_KEY: str


settings = Settings()
