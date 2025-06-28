#!/usr/bin/env python3
"""
Test script to verify PeerTube connection fixes
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.platforms.peertube import PeerTubePlatform

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_peertube_search():
    """Test PeerTube search functionality"""
    
    # Create config with test instances
    config = {
        "instances": [
            "https://peertube.heise.de",
            "https://video.ploud.fr",
            "https://peertube.tux.ovh",
            "https://tube.valinor.fr"
        ],
        "max_results_per_instance": 3,
        "http_timeout": 15,
        "http_connect_timeout": 10
    }
    
    # Create platform instance
    platform = PeerTubePlatform("peertube", config)
    
    try:
        # Initialize the platform
        await platform.initialize()
        
        print("\n" + "="*60)
        print("Testing PeerTube Search with Fixed Connection Handling")
        print("="*60 + "\n")
        
        # Test search
        search_query = "open source"
        print(f"Searching for: '{search_query}'")
        print("-" * 40)
        
        results = await platform.search_videos(search_query, max_results=10)
        
        if results:
            print(f"\n✓ Found {len(results)} videos total\n")
            
            # Group by instance
            instances = {}
            for result in results:
                instance = result.get('instance', 'unknown')
                if instance not in instances:
                    instances[instance] = []
                instances[instance].append(result)
            
            # Display results by instance
            for instance, videos in instances.items():
                print(f"\nFrom {instance}:")
                for video in videos[:2]:  # Show max 2 per instance
                    print(f"  - {video['title']}")
                    print(f"    Channel: {video['channel']}")
                    print(f"    Views: {video.get('views', 'N/A')}")
        else:
            print("\n✗ No results found")
        
        # Show health status
        print("\n" + "="*60)
        print("Instance Health Status:")
        print("="*60)
        health_status = platform.get_health_status()
        instance_health = health_status['instance_health']
        
        print(f"\nTotal instances: {instance_health['total_instances']}")
        print(f"Healthy instances: {instance_health['healthy_instances']}")
        print(f"Unhealthy instances: {len(instance_health['unhealthy_instances'])}")
        
        if instance_health['unhealthy_instances']:
            print(f"\nUnhealthy instances: {', '.join(instance_health['unhealthy_instances'])}")
        
        # Show circuit breaker status
        print("\n" + "="*60)
        print("Circuit Breaker Status:")
        print("="*60)
        cb_status = health_status['circuit_breakers']
        
        for instance, status in cb_status.items():
            state = status.get('state', 'unknown')
            failures = status.get('failure_count', 0)
            print(f"\n{instance}:")
            print(f"  State: {state}")
            print(f"  Failures: {failures}")
            print(f"  Success rate: {status['stats']['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"\n✗ Error during test: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await platform.cleanup()
        print("\n✓ Platform cleaned up")

if __name__ == "__main__":
    asyncio.run(test_peertube_search())