#!/usr/bin/env python3
"""
Test platforms directly within the Docker container
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, '/app/src')

from src.services.searcher import MultiPlatformSearcher
from src.platforms.registry import PlatformRegistry
from src.platforms.peertube import PeerTubePlatform
from src.platforms.odysee import OdyseePlatform
from src.platforms.rumble import RumblePlatform
from src.platforms.youtube import YouTubePlatform
from src.utils.config import load_config

async def test_platforms():
    print("🔍 Testing Platform Status in Docker")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    registry = PlatformRegistry()
    
    # Test each platform
    platform_configs = config.get('platforms', {})
    
    working_platforms = []
    
    for platform_name, platform_config in platform_configs.items():
        if not platform_config.get('enabled', False):
            print(f"❌ {platform_name.title()}: Disabled in config")
            continue
            
        try:
            # Create platform instance
            if platform_name == 'youtube':
                platform = YouTubePlatform(platform_config)
            elif platform_name == 'peertube':
                platform = PeerTubePlatform(platform_config)
            elif platform_name == 'odysee':
                platform = OdyseePlatform(platform_config)
            elif platform_name == 'rumble':
                platform = RumblePlatform(platform_config)
            else:
                print(f"⚠️  {platform_name.title()}: Unknown platform type")
                continue
                
            # Test basic functionality
            await platform.initialize()
            registry.register_platform(platform_name, platform)
            
            print(f"✅ {platform_name.title()}: Successfully initialized")
            
            # Test simple search
            try:
                results = await platform.search_videos("music", max_results=2)
                if results:
                    working_platforms.append(platform_name)
                    print(f"   📊 Search successful: {len(results)} results")
                    
                    # Show sample result
                    sample = results[0]
                    title = sample.get('title', 'No title')[:60]
                    channel = sample.get('channel', 'Unknown')[:30]
                    duration = sample.get('duration', 'Unknown')
                    views = sample.get('views', 'Unknown')
                    
                    print(f"   🎵 Sample: '{title}'")
                    print(f"       Channel: {channel}")
                    if duration != 'Unknown':
                        print(f"       Duration: {duration}")
                    if views != 'Unknown':
                        print(f"       Views: {views}")
                else:
                    print(f"   ⚠️  Search returned no results")
                    
            except Exception as e:
                print(f"   ❌ Search failed: {str(e)[:100]}")
                
        except Exception as e:
            print(f"❌ {platform_name.title()}: Failed to initialize - {str(e)[:100]}")
    
    print(f"\n📊 Summary: {len(working_platforms)} working platforms: {', '.join(working_platforms)}")
    
    # Test multi-platform searcher
    if working_platforms:
        print(f"\n🔍 Testing Multi-Platform Search")
        print("-" * 30)
        
        searcher = MultiPlatformSearcher(registry)
        
        try:
            results = await searcher.search_all_platforms("classical music", max_results=3)
            
            total_results = sum(len(platform_results) for platform_results in results.values())
            successful_platforms = [name for name, res in results.items() if res]
            
            print(f"✅ Multi-platform search successful!")
            print(f"   Total results: {total_results}")
            print(f"   Successful platforms: {', '.join(successful_platforms)}")
            
            # Show enhanced display format
            for platform_name, platform_results in results.items():
                if platform_results:
                    print(f"\n   📱 {platform_name.title()} Results:")
                    for i, result in enumerate(platform_results[:2], 1):
                        title = result.get('title', 'No title')
                        channel = result.get('channel', 'Unknown')
                        duration = result.get('duration', '')
                        views = result.get('views', '')
                        
                        # Enhanced format like Discord embed
                        desc_parts = [f"**{channel}**"]
                        if duration and duration != "Unknown":
                            desc_parts.append(f"({duration}")
                            if views and views != "Unknown views":
                                desc_parts.append(f" • {views})")
                            else:
                                desc_parts.append(")")
                        elif views and views != "Unknown views":
                            desc_parts.append(f"({views})")
                        
                        print(f"      {i}. {title}")
                        print(f"         {' '.join(desc_parts)}")
            
        except Exception as e:
            print(f"❌ Multi-platform search failed: {str(e)[:150]}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_platforms())