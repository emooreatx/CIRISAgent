import sys
from ciris_engine.main import main as ciris_main
import asyncio

if __name__ == "__main__":
    # Simulate CLI: --mode api --profile default --port 8080
    sys.argv = [
        "main.py",
        "--mode", "api",
        "--profile", "default",
        "--port", "8080"
    ]
    asyncio.run(ciris_main()) 
