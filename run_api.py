import asyncio
from typing import Optional
import click
from ciris_engine.main import main as engine_main

@click.command()
@click.option("--profile", default="default", help="Agent profile name")
@click.option("--config", type=click.Path(exists=True), help="Path to app config")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def run(profile: str, config: Optional[str], debug: bool) -> None:
    """Run the CIRIS Engine in API mode."""
    asyncio.run(engine_main.callback(mode="api", profile=profile, config=config, debug=debug))


if __name__ == "__main__":
    run()
