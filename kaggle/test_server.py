#!/usr/bin/env python3
"""
Test script to verify Kaggle inference server is working
Run this in a separate cell in Kaggle after the server starts
"""

import requests
import json

# Test the server
base_url = "https://zenia-heteronomous-sightlessly.ngrok-free.dev"

print("Testing Kaggle server...")

# 1. Check health
print("\n1. Health check:")
try:
    resp = requests.get(f"{base_url}/health", timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

# 2. Load model
print("\n2. Loading model:")
try:
    resp = requests.post(
        f"{base_url}/load",
        json={"model_name": "Orenguteng/Llama-3-8B-Lexi-Uncensored"},
        timeout=300
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

# 3. Test generation
print("\n3. Testing generation:")
try:
    resp = requests.post(
        f"{base_url}/generate",
        json={
            "prompt": "Hello, how are you?",
            "max_tokens": 50,
            "temperature": 0.7,
            "top_k": 50,
            "top_p": 0.9,
            "repetition_penalty": 1.2,
        },
        timeout=60
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
