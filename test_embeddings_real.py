import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

async def test_embed():
    async with httpx.AsyncClient() as client:
        print("Testing openai/text-embedding-3-small")
        resp = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "openai/text-embedding-3-small", "input": "test"}
        )
        print("Status:", resp.status_code)
        try:
            print("Body:", resp.json())
        except:
            print("Body raw:", resp.text)

asyncio.run(test_embed())
