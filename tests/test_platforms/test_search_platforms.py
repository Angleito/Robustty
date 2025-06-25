#!/usr/bin/env python3
"""
Test script to check which platforms are working and test search functionality
while YouTube is experiencing quota issues.
"""

import asyncio
import os
import sys
import logging
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.platforms.registry import PlatformRegistry
from src.platforms.peertube import PeerTube
from src.platforms.odysee import Odysee
from src.platforms.rumble import Rumble
from src.platforms.youtube import YouTube
from src.services.searcher import MultiPlatformSearcher
from src.utils.config import load_config


async def test_platform_availability():
    """Test which platforms are currently available and working"""
    print("🔍 Testing Platform Availability")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    
    # Initialize platform registry
    registry = PlatformRegistry()
    
    # Register platforms based on config
    platform_configs = config.get('platforms', {})
    
    # Test each platform
    for platform_name, platform_config in platform_configs.items():
        if not platform_config.get('enabled', False):
            print(f"❌ {platform_name.title()}: Disabled in config")
            continue
            
        try:
            # Create platform instance
            if platform_name == 'youtube':
                platform = YouTube(platform_config)
            elif platform_name == 'peertube':
                platform = PeerTube(platform_config)
            elif platform_name == 'odysee':
                platform = Odysee(platform_config)
            elif platform_name == 'rumble':
                platform = Rumble(platform_config)
            else:
                print(f"⚠️  {platform_name.title()}: Unknown platform type")
                continue
                
            # Test basic functionality
            await platform.initialize()
            registry.register_platform(platform_name, platform)
            
            print(f"✅ {platform_name.title()}: Successfully initialized")
            
            # Test search with a simple query
            try:
                test_query = "music"
                results = await platform.search_videos(test_query, max_results=3)
                if results:
                    print(f"   📊 Found {len(results)} results for '{test_query}'")
                    
                    # Show first result details
                    first_result = results[0]
                    title = first_result.get('title', 'No title')[:50]
                    channel = first_result.get('channel', 'Unknown')
                    duration = first_result.get('duration', 'Unknown')
                    views = first_result.get('views', 'Unknown')
                    
                    print(f"   🎵 Sample: '{title}' by {channel}")
                    if duration != 'Unknown':
                        print(f"      Duration: {duration}")
                    if views != 'Unknown':
                        print(f"      Views: {views}")
                else:
                    print(f"   ⚠️  No results found for '{test_query}'")
                    
            except Exception as e:
                print(f"   ❌ Search failed: {str(e)[:100]}")
                
        except Exception as e:
            print(f"❌ {platform_name.title()}: Failed to initialize - {str(e)[:100]}")
            
    print()
    return registry


async def test_enhanced_search_display():
    """Test the enhanced search display formatting"""
    print("🎨 Testing Enhanced Search Display")
    print("=" * 50)
    
    # Get platform registry
    registry = await test_platform_availability()
    
    # Initialize searcher
    searcher = MultiPlatformSearcher(registry)
    
    # Test queries
    test_queries = [
        "classical music",
        "jazz guitar",
        "electronic music"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing search for: '{query}'")
        print("-" * 30)
        
        try:
            results = await searcher.search_all_platforms(query, max_results=5)
            
            if not results or not any(results.values()):
                print("   ❌ No results found across all platforms")
                continue
                
            # Display results in enhanced format (mimicking the bot's display)
            total_results = sum(len(platform_results) for platform_results in results.values())
            working_platforms = [name for name, res in results.items() if res]
            
            print(f"   ✅ Found {total_results} results from {len(working_platforms)} platforms")
            print(f"   📂 Working platforms: {', '.join(working_platforms)}")
            
            # Show enhanced display format for each platform
            for platform_name, platform_results in results.items():
                if not platform_results:
                    continue
                    
                print(f"\n   📱 {platform_name.title()} Results:")
                
                for i, result in enumerate(platform_results[:3], 1):
                    title = result.get('title', 'No title')
                    channel = result.get('channel', 'Unknown')
                    duration = result.get('duration', '')
                    views = result.get('views', '')
                    url = result.get('url', '#')
                    
                    # Create enhanced description line (mimicking Discord embed format)
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
                    print(f"         🔗 {url}")
                    
        except Exception as e:
            print(f"   ❌ Search failed: {str(e)[:100]}")
            import traceback
            print(f"   📋 Debug: {traceback.format_exc()}")


async def test_fallback_mechanisms():
    """Test fallback mechanisms when some platforms are unavailable"""
    print("\n🔄 Testing Fallback Mechanisms")
    print("=" * 50)
    
    # Get platform registry
    registry = await test_platform_availability()
    searcher = MultiPlatformSearcher(registry)
    
    # Test search health status
    try:
        health_status = searcher.get_search_health_status()
        print("📊 Search Service Health Status:")
        print(f"   • Enabled platforms: {health_status.get('enabled_platforms', [])}")
        print(f"   • Total platforms: {health_status.get('total_platforms', 0)}")
        print(f"   • Registry status: {health_status.get('registry_status', 'unknown')}")
        
        resilience_status = health_status.get('resilience_status', {})
        if resilience_status:
            print(f"   • Resilience status: {len(resilience_status)} services monitored")
            
    except Exception as e:
        print(f"❌ Health status check failed: {e}")
        
    # Test with a specific query that might work on non-YouTube platforms
    print(f"\n🎯 Testing fallback with specific query:")
    try:
        results = await searcher.search_all_platforms("creative commons music", max_results=3)
        
        successful_platforms = [name for name, res in results.items() if res]
        failed_platforms = [name for name, res in results.items() if not res]
        
        print(f"   ✅ Successful platforms: {successful_platforms}")
        if failed_platforms:
            print(f"   ❌ Failed platforms: {failed_platforms}")
            
        # Test with URL detection
        print(f"\n🔗 Testing URL detection and platform routing:")
        test_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://framatube.org/w/abc123",
            "https://odysee.com/@channel:1/video:1",
            "https://rumble.com/v123-test-video.html"
        ]
        
        for url in test_urls:
            try:
                # Test URL detection
                video_info = searcher._extract_video_info(url)
                if video_info:
                    print(f"   ✅ Detected {video_info['platform']} URL: {video_info['id']}")
                else:
                    print(f"   ❌ Could not detect platform for: {url}")
            except Exception as e:
                print(f"   ❌ URL detection failed for {url}: {e}")
                
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")


async def main():
    """Main test function"""
    print("🚀 Robustty Platform Test Suite")
    print("Testing enhanced search improvements while YouTube is experiencing issues")
    print("=" * 80)
    
    # Set up logging to see debug info
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Test platform availability
        await test_platform_availability()
        
        # Test enhanced search display
        await test_enhanced_search_display()
        
        # Test fallback mechanisms
        await test_fallback_mechanisms()
        
        print("\n" + "=" * 80)
        print("✅ Test suite completed!")
        print("\n📋 Summary:")
        print("   • Platform availability tested")
        print("   • Enhanced search display formatting verified")  
        print("   • Fallback mechanisms evaluated")
        print("   • URL detection and routing tested")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())