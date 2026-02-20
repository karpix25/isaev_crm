import httpx
import json

api_key = "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"
models = [
    "google/gemini-embedding-001",
    "openai/text-embedding-3-small",
    "openai/text-embedding-ada-002",
    "qwen/qwen3-embedding-8b"
]

print(f"Testing {len(models)} models...")

for model in models:
    print(f"\n--- Testing Model: {model} ---")
    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/karpix25/isaev_crm",
                "X-Title": "Diagnostic Test"
            },
            json={
                "model": model,
                "input": "This is a test message to verify the embedding API is working."
            },
            timeout=15.0
        )
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            dim = len(data['data'][0]['embedding'])
            print(f"SUCCESS! Dimension: {dim}")
        else:
            print(f"FAILED: {r.text}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

print("\n--- Diagnostic Finished ---")
