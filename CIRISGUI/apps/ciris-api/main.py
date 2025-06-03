from ciris_engine.runtime.api_runtime import APIRuntime
import asyncio


def run_api(profile: str = "default", port: int = 8080) -> None:
    """Start the CIRIS API runtime."""

    async def _start() -> None:
        runtime = APIRuntime(profile_name=profile, port=port)
        await runtime.run()

    asyncio.run(_start())


if __name__ == "__main__":
    run_api()
