"""
Load generator for AutoSRE demo.

Continuously sends requests to the demo app to generate metrics.
"""

import asyncio
import os
import random
import httpx

TARGET_URL = os.getenv("TARGET_URL", "http://demo-app:8080")
REQUESTS_PER_SECOND = int(os.getenv("REQUESTS_PER_SECOND", "10"))


async def send_request(client: httpx.AsyncClient):
    """Send a single request."""
    try:
        # Mix of GET and POST requests
        if random.random() < 0.7:
            await client.get(f"{TARGET_URL}/api/data", timeout=10.0)
        else:
            await client.post(
                f"{TARGET_URL}/api/data",
                json={"test": "data", "random": random.randint(1, 100)},
                timeout=10.0
            )
    except Exception as e:
        pass  # Expected errors during failure modes


async def main():
    print(f"🔄 Load generator starting: {REQUESTS_PER_SECOND} req/s to {TARGET_URL}")
    
    delay = 1.0 / REQUESTS_PER_SECOND
    
    async with httpx.AsyncClient() as client:
        while True:
            asyncio.create_task(send_request(client))
            await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(main())
