#!/usr/bin/env python3
"""
Debug Docker environment variable loading
Run this inside the Docker container to diagnose token loading issues
"""

import os
import sys
from pathlib import Path

print("=== Docker Environment Debug ===")
print(f"Python: {sys.version}")
print(f"Working Directory: {os.getcwd()}")
print(f"Docker Container: {'Yes' if os.environ.get('DOCKER_CONTAINER') else 'No'}")
print()

# Check environment variables
print("Discord Environment Variables:")
for key, value in os.environ.items():
    if 'DISCORD' in key.upper():
        if len(value) > 20:
            print(f"  {key} = {value[:20]}... (length: {len(value)})")
        else:
            print(f"  {key} = {value}")

# Check .env files
print("\n.env Files:")
env_locations = [
    '.env',
    '/app/.env',
    '/.env',
    '/robustty/.env'
]

for loc in env_locations:
    path = Path(loc)
    if path.exists():
        print(f"\n  Found: {loc}")
        try:
            with open(path, 'r') as f:
                for line in f:
                    if 'DISCORD_TOKEN' in line:
                        parts = line.strip().split('=', 1)
                        if len(parts) == 2:
                            token = parts[1].strip().strip('"\'')
                            print(f"    DISCORD_TOKEN = {token[:20]}... (length: {len(token)})")
        except Exception as e:
            print(f"    Error reading: {e}")
    else:
        print(f"  Not found: {loc}")

# Test token loading
print("\nTesting Token Loading:")
try:
    # Import and use the enhanced loader
    sys.path.insert(0, '/app')
    from src.utils.env_loader import load_discord_token, validate_token
    
    token = load_discord_token()
    if token:
        print(f"  ✓ Token loaded: {token[:20]}... (length: {len(token)})")
        if validate_token(token):
            print("  ✓ Token validation: PASSED")
        else:
            print("  ✗ Token validation: FAILED")
    else:
        print("  ✗ Token loading: FAILED")
except Exception as e:
    print(f"  ✗ Error: {e}")

# Check docker-compose passed variables
print("\nDocker Compose Variables:")
compose_vars = ['DISCORD_TOKEN', 'REDIS_URL', 'LOG_LEVEL']
for var in compose_vars:
    value = os.environ.get(var, 'NOT SET')
    if var == 'DISCORD_TOKEN' and value != 'NOT SET':
        print(f"  {var} = {value[:20]}...")
    else:
        print(f"  {var} = {value}")

print("\n=== End Debug ===")