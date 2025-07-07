#!/usr/bin/env python3
"""
Test script for YouTube Music headless integration with Discord bot.

This script tests the complete Docker deployment and integration of YouTube Music
headless service with the Discord bot.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional


class YouTubeMusicIntegrationTester:
    def __init__(self):
        self.base_url = "http://localhost"
        self.ytmusic_port = 9863
        self.health_port = 8080
        self.results = []
        
    async def test_youtube_music_service(self) -> Dict[str, Any]:
        """Test YouTube Music headless service directly"""
        print("\n🎵 Testing YouTube Music Headless Service...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test health endpoint
                health_url = f"{self.base_url}:{self.ytmusic_port}/api/health"
                async with session.get(health_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ YouTube Music service is healthy: {data}")
                        return {
                            "test": "youtube_music_service",
                            "status": "passed",
                            "details": data
                        }
                    else:
                        print(f"❌ YouTube Music service health check failed: {response.status}")
                        return {
                            "test": "youtube_music_service",
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            print(f"❌ YouTube Music service test failed: {e}")
            return {
                "test": "youtube_music_service",
                "status": "failed",
                "error": str(e)
            }
    
    async def test_bot_health_endpoints(self) -> Dict[str, Any]:
        """Test bot health endpoints"""
        print("\n🤖 Testing Bot Health Endpoints...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test general health
                health_url = f"{self.base_url}:{self.health_port}/health"
                async with session.get(health_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Bot health check passed: {data}")
                        
                        # Test YouTube Music specific health
                        ytm_health_url = f"{self.base_url}:{self.health_port}/health/youtube-music"
                        async with session.get(ytm_health_url) as ytm_response:
                            if ytm_response.status == 200:
                                ytm_data = await ytm_response.json()
                                print(f"✅ YouTube Music integration health: {ytm_data}")
                                return {
                                    "test": "bot_health_endpoints",
                                    "status": "passed",
                                    "details": {
                                        "general_health": data,
                                        "youtube_music_health": ytm_data
                                    }
                                }
                            else:
                                print(f"⚠️  YouTube Music health endpoint returned: {ytm_response.status}")
                                return {
                                    "test": "bot_health_endpoints",
                                    "status": "partial",
                                    "details": {
                                        "general_health": data,
                                        "youtube_music_health": f"HTTP {ytm_response.status}"
                                    }
                                }
                    else:
                        print(f"❌ Bot health check failed: {response.status}")
                        return {
                            "test": "bot_health_endpoints",
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            print(f"❌ Bot health endpoints test failed: {e}")
            return {
                "test": "bot_health_endpoints",
                "status": "failed",
                "error": str(e)
            }
    
    async def test_platform_registration(self) -> Dict[str, Any]:
        """Test platform registration and priority"""
        print("\n📋 Testing Platform Registration...")
        
        try:
            async with aiohttp.ClientSession() as session:
                platforms_url = f"{self.base_url}:{self.health_port}/health/platforms"
                async with session.get(platforms_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check if YouTube Music is registered
                        if 'platforms' in data:
                            platforms = data['platforms']
                            if 'youtube_music_headless' in platforms:
                                ytm_platform = platforms['youtube_music_headless']
                                if ytm_platform.get('enabled'):
                                    print(f"✅ YouTube Music headless is registered and enabled")
                                    
                                    # Check priority order
                                    platform_order = list(platforms.keys())
                                    if platform_order[0] == 'youtube_music_headless':
                                        print(f"✅ YouTube Music headless has highest priority")
                                        return {
                                            "test": "platform_registration",
                                            "status": "passed",
                                            "details": {
                                                "platforms": platforms,
                                                "priority_order": platform_order
                                            }
                                        }
                                    else:
                                        print(f"⚠️  YouTube Music headless is not first priority: {platform_order}")
                                        return {
                                            "test": "platform_registration",
                                            "status": "partial",
                                            "warning": "YouTube Music not first priority",
                                            "details": {
                                                "platforms": platforms,
                                                "priority_order": platform_order
                                            }
                                        }
                                else:
                                    print(f"❌ YouTube Music headless is disabled")
                                    return {
                                        "test": "platform_registration",
                                        "status": "failed",
                                        "error": "YouTube Music headless is disabled"
                                    }
                            else:
                                print(f"❌ YouTube Music headless not found in platforms")
                                return {
                                    "test": "platform_registration",
                                    "status": "failed",
                                    "error": "YouTube Music headless not registered"
                                }
                        else:
                            print(f"❌ No platforms data in response")
                            return {
                                "test": "platform_registration",
                                "status": "failed",
                                "error": "No platforms data"
                            }
                    else:
                        print(f"❌ Platform status check failed: {response.status}")
                        return {
                            "test": "platform_registration",
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            print(f"❌ Platform registration test failed: {e}")
            return {
                "test": "platform_registration",
                "status": "failed",
                "error": str(e)
            }
    
    async def test_cookie_integration(self) -> Dict[str, Any]:
        """Test cookie integration for YouTube Music"""
        print("\n🍪 Testing Cookie Integration...")
        
        try:
            async with aiohttp.ClientSession() as session:
                cookie_health_url = f"{self.base_url}:{self.health_port}/health/cookies/youtube_music"
                async with session.get(cookie_health_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Cookie health check passed: {data}")
                        return {
                            "test": "cookie_integration",
                            "status": "passed",
                            "details": data
                        }
                    elif response.status == 404:
                        print(f"⚠️  YouTube Music cookies not found (may be normal if not authenticated)")
                        return {
                            "test": "cookie_integration",
                            "status": "warning",
                            "details": "No cookies found - platform may work without authentication"
                        }
                    else:
                        print(f"❌ Cookie health check failed: {response.status}")
                        return {
                            "test": "cookie_integration",
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            print(f"❌ Cookie integration test failed: {e}")
            return {
                "test": "cookie_integration",
                "status": "failed",
                "error": str(e)
            }
    
    async def test_search_functionality(self) -> Dict[str, Any]:
        """Test search through YouTube Music API"""
        print("\n🔍 Testing Search Functionality...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test direct YouTube Music API search
                search_url = f"{self.base_url}:{self.ytmusic_port}/api/search"
                params = {"q": "test", "limit": 5, "type": "songs"}
                
                async with session.get(search_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'results' in data and len(data['results']) > 0:
                            print(f"✅ Search returned {len(data['results'])} results")
                            return {
                                "test": "search_functionality",
                                "status": "passed",
                                "details": {
                                    "result_count": len(data['results']),
                                    "first_result": data['results'][0] if data['results'] else None
                                }
                            }
                        else:
                            print(f"⚠️  Search returned no results")
                            return {
                                "test": "search_functionality",
                                "status": "warning",
                                "details": "No search results returned"
                            }
                    else:
                        print(f"❌ Search request failed: {response.status}")
                        return {
                            "test": "search_functionality",
                            "status": "failed",
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            print(f"❌ Search functionality test failed: {e}")
            return {
                "test": "search_functionality",
                "status": "failed",
                "error": str(e)
            }
    
    async def run_all_tests(self):
        """Run all integration tests"""
        print("=" * 60)
        print("🎵 YouTube Music Headless Integration Test Suite")
        print("=" * 60)
        print(f"Started at: {datetime.now().isoformat()}")
        
        # Wait a moment for services to stabilize
        print("\n⏳ Waiting for services to stabilize...")
        await asyncio.sleep(5)
        
        # Run all tests
        tests = [
            self.test_youtube_music_service(),
            self.test_bot_health_endpoints(),
            self.test_platform_registration(),
            self.test_cookie_integration(),
            self.test_search_functionality()
        ]
        
        results = await asyncio.gather(*tests, return_exceptions=True)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        
        passed = 0
        failed = 0
        warnings = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                print(f"❌ Test crashed: {result}")
            elif result['status'] == 'passed':
                passed += 1
                print(f"✅ {result['test']}: PASSED")
            elif result['status'] == 'warning' or result['status'] == 'partial':
                warnings += 1
                print(f"⚠️  {result['test']}: WARNING - {result.get('details', result.get('warning', 'Unknown'))}")
            else:
                failed += 1
                print(f"❌ {result['test']}: FAILED - {result.get('error', 'Unknown error')}")
        
        print(f"\nTotal: {len(results)} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warnings: {warnings}")
        
        # Save results to file
        with open('youtube_music_integration_test_results.json', 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": len(results),
                    "passed": passed,
                    "failed": failed,
                    "warnings": warnings
                },
                "results": results
            }, f, indent=2)
        
        print(f"\n💾 Results saved to: youtube_music_integration_test_results.json")
        
        return failed == 0


async def main():
    """Main test runner"""
    tester = YouTubeMusicIntegrationTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! YouTube Music integration is working correctly.")
        exit(0)
    else:
        print("\n⚠️  Some tests failed. Please check the logs above.")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())