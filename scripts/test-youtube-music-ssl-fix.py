#!/usr/bin/env python3
"""
Test script to verify YouTube Music SSL handshake timeout fixes.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, Any
import httpx
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# YouTube Music API configuration
YOUTUBE_MUSIC_API_URL = "http://localhost:9863"
YOUTUBE_MUSIC_API_URL_DOCKER = "http://youtube-music-headless:9863"

class YouTubeMusicSSLTester:
    """Test YouTube Music SSL fixes"""
    
    def __init__(self, base_url: str = YOUTUBE_MUSIC_API_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=90.0)
        self.results = []
    
    async def test_health_check(self) -> Dict[str, Any]:
        """Test the health check endpoint"""
        test_name = "Health Check"
        logger.info(f"Testing {test_name}...")
        
        try:
            start_time = time.time()
            response = await self.client.get(f"{self.base_url}/api/health")
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    "test": test_name,
                    "status": "PASS",
                    "duration": f"{duration:.2f}s",
                    "response": data
                }
                logger.info(f"✅ {test_name} passed in {duration:.2f}s")
            else:
                result = {
                    "test": test_name,
                    "status": "FAIL",
                    "duration": f"{duration:.2f}s",
                    "error": f"HTTP {response.status_code}"
                }
                logger.error(f"❌ {test_name} failed: HTTP {response.status_code}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            result = {
                "test": test_name,
                "status": "ERROR",
                "error": str(e)
            }
            logger.error(f"❌ {test_name} error: {e}")
            self.results.append(result)
            return result
    
    async def test_auth_status(self) -> Dict[str, Any]:
        """Test the auth status endpoint"""
        test_name = "Auth Status"
        logger.info(f"Testing {test_name}...")
        
        try:
            start_time = time.time()
            response = await self.client.get(f"{self.base_url}/api/auth/status")
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    "test": test_name,
                    "status": "PASS",
                    "duration": f"{duration:.2f}s",
                    "response": data
                }
                logger.info(f"✅ {test_name} passed in {duration:.2f}s")
            else:
                result = {
                    "test": test_name,
                    "status": "FAIL",
                    "duration": f"{duration:.2f}s",
                    "error": f"HTTP {response.status_code}"
                }
                logger.error(f"❌ {test_name} failed: HTTP {response.status_code}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            result = {
                "test": test_name,
                "status": "ERROR",
                "error": str(e)
            }
            logger.error(f"❌ {test_name} error: {e}")
            self.results.append(result)
            return result
    
    async def test_search_simple(self) -> Dict[str, Any]:
        """Test a simple search that was previously failing"""
        test_name = "Simple Search"
        logger.info(f"Testing {test_name}...")
        
        try:
            start_time = time.time()
            response = await self.client.get(
                f"{self.base_url}/api/search",
                params={"q": "test", "limit": 1}
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    "test": test_name,
                    "status": "PASS",
                    "duration": f"{duration:.2f}s",
                    "response": {
                        "results_count": len(data.get("results", [])),
                        "first_result": data.get("results", [{}])[0] if data.get("results") else None
                    }
                }
                logger.info(f"✅ {test_name} passed in {duration:.2f}s - Found {len(data.get('results', []))} results")
            else:
                result = {
                    "test": test_name,
                    "status": "FAIL",
                    "duration": f"{duration:.2f}s",
                    "error": f"HTTP {response.status_code}",
                    "response_text": response.text
                }
                logger.error(f"❌ {test_name} failed: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            result = {
                "test": test_name,
                "status": "ERROR",
                "error": str(e)
            }
            logger.error(f"❌ {test_name} error: {e}")
            self.results.append(result)
            return result
    
    async def test_search_multiple(self) -> Dict[str, Any]:
        """Test a more complex search"""
        test_name = "Multiple Results Search"
        logger.info(f"Testing {test_name}...")
        
        try:
            start_time = time.time()
            response = await self.client.get(
                f"{self.base_url}/api/search",
                params={"q": "music", "limit": 5}
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                result = {
                    "test": test_name,
                    "status": "PASS",
                    "duration": f"{duration:.2f}s",
                    "response": {
                        "results_count": len(data.get("results", [])),
                        "sample_titles": [r.get("title", "Unknown") for r in data.get("results", [])[:3]]
                    }
                }
                logger.info(f"✅ {test_name} passed in {duration:.2f}s - Found {len(data.get('results', []))} results")
            else:
                result = {
                    "test": test_name,
                    "status": "FAIL",
                    "duration": f"{duration:.2f}s",
                    "error": f"HTTP {response.status_code}",
                    "response_text": response.text
                }
                logger.error(f"❌ {test_name} failed: HTTP {response.status_code}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            result = {
                "test": test_name,
                "status": "ERROR",
                "error": str(e)
            }
            logger.error(f"❌ {test_name} error: {e}")
            self.results.append(result)
            return result
    
    async def test_network_connectivity(self) -> Dict[str, Any]:
        """Test network connectivity to YouTube"""
        test_name = "Network Connectivity"
        logger.info(f"Testing {test_name}...")
        
        try:
            start_time = time.time()
            
            # Test basic connectivity
            import socket
            socket.gethostbyname('www.youtube.com')
            
            # Test HTTPS connection
            response = await self.client.get('https://www.youtube.com', timeout=30.0)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                result = {
                    "test": test_name,
                    "status": "PASS",
                    "duration": f"{duration:.2f}s",
                    "response": "Successfully connected to YouTube"
                }
                logger.info(f"✅ {test_name} passed in {duration:.2f}s")
            else:
                result = {
                    "test": test_name,
                    "status": "FAIL",
                    "duration": f"{duration:.2f}s",
                    "error": f"HTTP {response.status_code}"
                }
                logger.error(f"❌ {test_name} failed: HTTP {response.status_code}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            result = {
                "test": test_name,
                "status": "ERROR",
                "error": str(e)
            }
            logger.error(f"❌ {test_name} error: {e}")
            self.results.append(result)
            return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests"""
        logger.info("🚀 Starting YouTube Music SSL Fix Tests")
        logger.info(f"Testing API at: {self.base_url}")
        
        # Run tests in order
        await self.test_health_check()
        await self.test_auth_status()
        await self.test_network_connectivity()
        await self.test_search_simple()
        await self.test_search_multiple()
        
        # Generate summary
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r["status"] == "PASS"])
        failed_tests = len([r for r in self.results if r["status"] == "FAIL"])
        error_tests = len([r for r in self.results if r["status"] == "ERROR"])
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "errors": error_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%",
            "results": self.results
        }
        
        logger.info(f"📊 Test Summary: {passed_tests}/{total_tests} passed ({summary['success_rate']})")
        
        if failed_tests > 0 or error_tests > 0:
            logger.error(f"❌ {failed_tests} tests failed, {error_tests} tests had errors")
        else:
            logger.info("🎉 All tests passed!")
        
        return summary
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

async def main():
    """Main test function"""
    # Check if we should test Docker internal URL
    test_docker = len(sys.argv) > 1 and sys.argv[1] == "docker"
    
    if test_docker:
        api_url = YOUTUBE_MUSIC_API_URL_DOCKER
        logger.info("Testing Docker internal URL")
    else:
        api_url = YOUTUBE_MUSIC_API_URL
        logger.info("Testing localhost URL")
    
    tester = YouTubeMusicSSLTester(api_url)
    
    try:
        summary = await tester.run_all_tests()
        
        # Print results
        print(f"\\n{'='*60}")
        print("YOUTUBE MUSIC SSL FIX TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['errors']}")
        print(f"Success Rate: {summary['success_rate']}")
        print(f"{'='*60}")
        
        # Save results to file
        with open('youtube-music-ssl-test-results.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info("Results saved to youtube-music-ssl-test-results.json")
        
        # Exit with appropriate code
        if summary['failed'] > 0 or summary['errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Test runner error: {e}")
        sys.exit(1)
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())