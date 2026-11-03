"""Local-only configuration; credentials never enter task payloads or results."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from .domain import ResearchError

PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


@dataclass(frozen=True)
class Settings:
    key: str = field(default="", repr=False)
    secret: str = field(default="", repr=False)
    sec_agent: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.key and self.secret)

    def headers(self) -> dict[str, str]:
        if not self.configured:
            raise ResearchError(
                "Add your Alpaca paper API keys to the local .env file, then try again. Keys are never stored in research results."
            )
        return {"APCA-API-KEY-ID": self.key, "APCA-API-SECRET-KEY": self.secret}


def settings() -> Settings:
    path = Path(os.environ.get("APERTURE_ENV_FILE", ".env"))
    local = dotenv_values(path) if path.is_file() else {}

    def get(name: str) -> str:
        return str(os.environ.get(name, local.get(name)) or "").strip()

    return Settings(
        get("ALPACA_API_KEY"), get("ALPACA_SECRET_KEY"), get("SEC_USER_AGENT")
    )
