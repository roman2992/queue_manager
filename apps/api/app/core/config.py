from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_exp_minutes: int = 60 * 24 * 7
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
