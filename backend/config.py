"""Runtime configuration, loaded from environment / .env.

Nothing here is required. With no API key the app runs in deterministic
fallback mode; everything else has sensible defaults tuned for a live demo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # .env is convenient but optional
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv missing is fine
    pass


def _get(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    narration_model: str
    investigator_model: str
    investigator_effort: str
    tick_interval: float
    window_size: int
    contamination: float
    default_scenario: str
    data_source: str

    @property
    def llm_enabled(self) -> bool:
        """True when a Claude API key is present."""
        return bool(self.anthropic_api_key)


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        narration_model=_get("NARRATION_MODEL", "claude-opus-4-8"),
        investigator_model=_get("INVESTIGATOR_MODEL", "claude-opus-4-8"),
        investigator_effort=_get("INVESTIGATOR_EFFORT", "high"),
        tick_interval=float(_get("TICK_INTERVAL", "1.5")),
        window_size=int(_get("WINDOW_SIZE", "180")),
        contamination=float(_get("ANOMALY_CONTAMINATION", "0.03")),
        default_scenario=_get("DEFAULT_SCENARIO", "nominal"),
        data_source=_get("DATA_SOURCE", "simulator"),
    )


settings = load_settings()
