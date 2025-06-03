"""Auto-generated wise authority stub."""
from ciris_adk import WiseAuthorityService

class TestWa(WiseAuthorityService):
    async def fetch_guidance(self, context: dict) -> str | None:
        return None

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        return False
