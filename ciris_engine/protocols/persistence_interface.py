from abc import ABC, abstractmethod
from typing import Any

class PersistenceInterface(ABC):
    """Minimal persistence interface."""

    @abstractmethod
    def save_state(self, key: str, data: Any) -> None:
        ...

    @abstractmethod
    def load_state(self, key: str) -> Any:
        ...
