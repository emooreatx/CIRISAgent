import pytest
from unittest.mock import MagicMock
from ciris_engine.services.cli_service import CLIService

class DummyDispatcher:
    def register_service_handler(self, name, handler):
        self.handler = handler

def test_cli_service_init():
    dispatcher = DummyDispatcher()
    service = CLIService(dispatcher)
    assert service.action_dispatcher is dispatcher
    assert hasattr(dispatcher, "handler")
