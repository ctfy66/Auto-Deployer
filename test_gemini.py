"""Quick test script to verify Gemini API connectivity."""
import json
import requests

API_KEY = "AIzaSyDGtKLy2asnCEflQDMqzfMI8GOr6MktZoA"
MODEL = "gemini-1.5-pro"

url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

body = {
    "contents": [
        {
            "role": "user",
            "parts": [{"text": "Say hello in JSON format: {\"message\": \"...\"}"}],
        }
    ],
    "generationConfig": {
        "temperature": 0.0,
        "responseMimeType": "application/json",
    },
}

print(f"Testing Gemini API...")
print(f"URL: {url[:80]}...")

try:
    response = requests.post(url, json=body, timeout=60)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
