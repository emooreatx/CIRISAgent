"""Shared model primitives for the CIRIS ADK."""

from __future__ import annotations

from enum import StrEnum
from datetime import datetime
from typing import Any, Dict, TypedDict, Optional, Protocol, List

from pydantic import BaseModel, Field


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

