import asyncio
import traceback
from src.services.openrouter_service import openrouter_service
import logging

logging.basicConfig(level=logging.DEBUG)

async def test():
    try:
        print("Starting test...")
        res = await openrouter_service.generate_embeddings("test")
        print("Success, length:", len(res))
    except Exception as e:
        print("Exception caught:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
