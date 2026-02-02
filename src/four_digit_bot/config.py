from pathlib import Path
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    bot_token: str = Field(validation_alias="BOT_TOKEN")
    allowed_user_ids_raw: str = Field(default="", validation_alias="ALLOWED_USER_IDS")
    # use a dummy alias so env doesn't try to JSON-parse this list field
    allowed_user_ids: List[int] = Field(default_factory=list, validation_alias="ALLOWED_USER_IDS_PARSED")
    winning_codes: int = Field(default=88, validation_alias="WINNING_CODES")
    total_codes: int = Field(default=10000, validation_alias="TOTAL_CODES")
    database_path: Path = Path("data/state.db")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @model_validator(mode="after")
    def parse_allowed_ids(self):
        raw = self.allowed_user_ids_raw
        if raw is None or raw == "":
            self.allowed_user_ids = []
        else:
            self.allowed_user_ids = [int(v.strip()) for v in str(raw).split(",") if v.strip()]
        return self


def load_settings() -> Settings:
    return Settings()
