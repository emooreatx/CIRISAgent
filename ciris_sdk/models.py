from __future__ import annotations

from typing import Optional, List, Any
from pydantic import BaseModel

class Message(BaseModel):
    id: str
    content: str
    author_id: str
    author_name: str
    channel_id: str
    timestamp: Optional[str] = None

class MemoryEntry(BaseModel):
    key: str
    value: Any

class MemoryScope(BaseModel):
    name: str
    entries: Optional[List[MemoryEntry]] = None
