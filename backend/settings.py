from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "ireland_after_dark"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    geocoding_url: str = 'https://nominatim.openstreetmap.org/search'


settings = Settings()
