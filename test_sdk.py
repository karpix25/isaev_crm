import asyncio
from openrouter import OpenRouter

async def test():
    client = OpenRouter(api_key="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")
    try:
        res = await client.embeddings.generate_async(input="test", model="openai/text-embedding-3-small")
        print("Success!")
        print(len(res.data[0].embedding) if res.data else "No data")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
