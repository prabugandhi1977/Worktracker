from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://worktrack:worktrack@postgres:5432/worktrack"

    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "company/+/+/rfid/events"
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None

    DEBOUNCE_SECONDS: int = 30
    NORMAL_DAILY_HOURS: float = 8.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
