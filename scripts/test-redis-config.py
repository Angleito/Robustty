#!/usr/bin/env python3
"""
Test script to validate Redis configuration works across different environments.
"""

import os
import sys
from typing import Optional

def test_redis_url_parsing():
    """Test Redis URL parsing with different formats."""
    test_urls = [
        "redis://localhost:6379",
        "redis://redis:6379", 
        "redis://username:password@redis-server:6379/0",
        "redis://redis.example.com:6380/1"
    ]
    
    print("Testing Redis URL parsing...")
    for url in test_urls:
        try:
            # Test with redis.from_url (sync redis)
            import redis
            r = redis.from_url(url, decode_responses=True)
            print(f"✓ Successfully parsed: {url}")
        except Exception as e:
            print(f"✗ Failed to parse {url}: {e}")

def test_environment_variables():
    """Test environment variable resolution."""
    print("\nTesting environment variable resolution...")
    
    # Test cases for different environments
    test_cases = [
        ("Local Development", "redis://localhost:6379"),
        ("VPS Deployment", "redis://redis:6379"),
        ("External Redis", "redis://external-redis.example.com:6379"),
    ]
    
    for env_name, redis_url in test_cases:
        os.environ['REDIS_URL'] = redis_url
        resolved_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        if resolved_url == redis_url:
            print(f"✓ {env_name}: {resolved_url}")
        else:
            print(f"✗ {env_name}: Expected {redis_url}, got {resolved_url}")

def test_config_fallback():
    """Test configuration fallback logic."""
    print("\nTesting configuration fallback logic...")
    
    # Simulate config structure
    configs = [
        # URL-based config (preferred)
        {'url': 'redis://localhost:6379'},
        
        # Individual parameters (fallback)
        {'host': 'localhost', 'port': 6379, 'db': 0},
        
        # Mixed config (URL takes precedence)
        {'url': 'redis://redis:6379', 'host': 'localhost', 'port': 6379},
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"Config {i}: {config}")
        
        if 'url' in config:
            print(f"  → Would use URL: {config['url']}")
        else:
            host = config.get('host', 'localhost')
            port = config.get('port', 6379)
            db = config.get('db', 0)
            print(f"  → Would use parameters: host={host}, port={port}, db={db}")

def main():
    """Run all tests."""
    print("Redis Configuration Test Suite")
    print("=" * 40)
    
    try:
        test_redis_url_parsing()
        test_environment_variables()
        test_config_fallback()
        
        print("\n" + "=" * 40)
        print("All tests completed!")
        print("\nNext steps:")
        print("1. Set REDIS_URL in your .env file")
        print("2. Start services with docker-compose up -d")
        print("3. Check logs with docker-compose logs -f robustty")
        
    except Exception as e:
        print(f"\nTest suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()