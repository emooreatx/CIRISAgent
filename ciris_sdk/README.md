# CIRIS SDK

Async client library for interacting with a running CIRIS Engine instance.

```python
from ciris_sdk import CIRISClient

async def main():
    async with CIRISClient(base_url="http://localhost:8080") as client:
        await client.messages.send("hello")
```
