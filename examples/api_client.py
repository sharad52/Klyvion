"""Minimal client for the Klyvion HTTP server (klyvion serve)."""

import requests

BASE = "http://localhost:8000"

print(requests.get(f"{BASE}/voices").json())

resp = requests.post(
    f"{BASE}/synthesize",
    json={"text": "Hello from the REST API!", "voice": "man"},
)
resp.raise_for_status()
with open("api_demo.wav", "wb") as f:
    f.write(resp.content)
print("Wrote api_demo.wav")
