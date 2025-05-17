#!/usr/bin/env python3
import requests
import json

# Test the stream service with a known good YouTube video ID
video_id = "VNdHd1asf9s"  # Full 11-character ID
url = f"http://localhost:5001/stream/youtube/{video_id}"

print(f"Testing stream service with video ID: {video_id}")
print(f"URL: {url}")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")

# Test with a truncated ID to see the error
print("\n\nTesting with truncated ID:")
truncated_id = "j89Qu0xu18"  # This was the problematic ID
url = f"http://localhost:5001/stream/youtube/{truncated_id}"
print(f"URL: {url}")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Exception: {e}")