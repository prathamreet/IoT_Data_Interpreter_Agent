"""Request/response schemas for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel


class ScenarioRequest(BaseModel):
    scenario: str


class InvestigateRequest(BaseModel):
    sensor_id: str | None = None
    focus: str | None = None


class ReportRequest(BaseModel):
    report_markdown: str | None = None
    used_llm: bool = False
    model: str | None = None
