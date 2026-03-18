from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    ANTHROPIC_API_KEY: str
    RAKUTEN_APP_ID: str
    # Legacy web-app credentials — only required for browser-side (JavaScript) calls
    RAKUTEN_ACCESS_KEY: str = ""
    APP_ORIGIN: str = "https://moodmeshi.vercel.app"

    # Slack Bot credentials (optional — leave empty to disable Slack integration)
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""

    # Database (optional — leave empty to disable DB features)
    DATABASE_URL: str = ""


settings = Settings()
