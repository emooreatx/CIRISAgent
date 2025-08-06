"""Shared model primitives for the CIRIS ADK."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Outcome(StrEnum):
    OK = "OK"
    ERROR = "ERROR"
    DEFERRED = "DEFERRED"
    BLOCKED = "BLOCKED"


class GuardrailHit(BaseModel):
    guardrail_id: str
    message: str


class Stakeholder(BaseModel):
    id: str
    display_name: str | None = None
