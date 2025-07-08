#!/usr/bin/env python3
"""
YouTube Music Headless Service Connectivity Test for VPS
Tests connection to the YouTube Music headless container and diagnoses issues.
"""

import asyncio
import aiohttp
import json
import socket
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional, List


class YouTubeMusicTester:
    def __init__(self, api_url: str = "http://youtube-music-headless:9863"):
        self.api_url = api_url
        self.results: List[Dict[str, Any]] = []
        
    async def test_dns_resolution(self) -> Dict[str, Any]:
        """Test DNS resolution for the YouTube Music service"""
        print("\n🔍 Testing DNS Resolution...")
        
        try:
            # Extract hostname from URL
            import urllib.parse
            parsed = urllib.parse.urlparse(self.api_url)
            hostname = parsed.hostname or "youtube-music-headless"
            
            # Try to resolve hostname
            start_time = time.time()
            ip_address = socket.gethostbyname(hostname)
            resolution_time = time.time() - start_time
            
            result = {
                "test": "DNS Resolution",
                "status": "PASS",
                "hostname": hostname,
                "ip_address": ip_address,
                "resolution_time_ms": round(resolution_time * 1000, 2),
                "message": f"Successfully resolved {hostname} to {ip_address}"
            }
            print(f"✅ {result['message']} ({result['resolution_time_ms']}ms)")
            
        except socket.gaierror as e:
            result = {
                "test": "DNS Resolution",
                "status": "FAIL",
                "hostname": hostname,
                "error": str(e),
                "message": f"Failed to resolve {hostname}: {e}"
            }
            print(f"❌ {result['message']}")
            
        except Exception as e:
            result = {
                "test": "DNS Resolution",
                "status": "ERROR",
                "error": str(e),
                "message": f"Unexpected error during DNS resolution: {e}"
            }
            print(f"❌ {result['message']}")
            
        self.results.append(result)
        return result
        
    async def test_tcp_connection(self) -> Dict[str, Any]:
        """Test raw TCP connection to the service"""
        print("\n🔌 Testing TCP Connection...")
        
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(self.api_url)
            hostname = parsed.hostname or "youtube-music-headless"
            port = parsed.port or 9863
            
            # Create socket and test connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            start_time = time.time()
            result_code = sock.connect_ex((hostname, port))
            connection_time = time.time() - start_time
            sock.close()
            
            if result_code == 0:
                result = {
                    "test": "TCP Connection",
                    "status": "PASS",
                    "host": f"{hostname}:{port}",
                    "connection_time_ms": round(connection_time * 1000, 2),
                    "message": f"Successfully connected to {hostname}:{port}"
                }
                print(f"✅ {result['message']} ({result['connection_time_ms']}ms)")
            else:
                result = {
                    "test": "TCP Connection",
                    "status": "FAIL",
                    "host": f"{hostname}:{port}",
                    "error_code": result_code,
                    "message": f"Failed to connect to {hostname}:{port} (error code: {result_code})"
                }
                print(f"❌ {result['message']}")
                
        except Exception as e:
            result = {
                "test": "TCP Connection",
                "status": "ERROR",
                "error": str(e),
                "message": f"Unexpected error during TCP connection: {e}"
            }
            print(f"❌ {result['message']}")
            
        self.results.append(result)
        return result
        
    async def test_health_endpoint(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test the health endpoint"""
        print("\n💓 Testing Health Endpoint...")
        
        endpoint = f"{self.api_url}/api/health"
        
        try:
            start_time = time.time()
            async with session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    result = {
                        "test": "Health Endpoint",
                        "status": "PASS",
                        "http_status": response.status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "health_data": data,
                        "message": f"Health check passed: {data.get('status', 'unknown')}"
                    }
                    print(f"✅ {result['message']} ({result['response_time_ms']}ms)")
                else:
                    text = await response.text()
                    result = {
                        "test": "Health Endpoint",
                        "status": "FAIL",
                        "http_status": response.status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "response_body": text[:200],
                        "message": f"Health check failed with status {response.status}"
                    }
                    print(f"❌ {result['message']}")
                    
        except asyncio.TimeoutError:
            result = {
                "test": "Health Endpoint",
                "status": "TIMEOUT",
                "message": "Health check timed out after 10 seconds"
            }
            print(f"⏱️ {result['message']}")
            
        except aiohttp.ClientError as e:
            result = {
                "test": "Health Endpoint",
                "status": "ERROR",
                "error": str(e),
                "error_type": type(e).__name__,
                "message": f"Client error during health check: {e}"
            }
            print(f"❌ {result['message']}")
            
        except Exception as e:
            result = {
                "test": "Health Endpoint",
                "status": "ERROR",
                "error": str(e),
                "error_type": type(e).__name__,
                "message": f"Unexpected error during health check: {e}"
            }
            print(f"❌ {result['message']}")
            
        self.results.append(result)
        return result
        
    async def test_search_functionality(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test search endpoint with a sample query"""
        print("\n🔎 Testing Search Functionality...")
        
        endpoint = f"{self.api_url}/api/search"
        params = {"q": "test", "limit": 1}
        
        try:
            start_time = time.time()
            async with session.get(
                endpoint,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    results_count = len(data.get("results", []))
                    result = {
                        "test": "Search Functionality",
                        "status": "PASS",
                        "http_status": response.status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "results_count": results_count,
                        "message": f"Search successful, found {results_count} results"
                    }
                    print(f"✅ {result['message']} ({result['response_time_ms']}ms)")
                else:
                    text = await response.text()
                    result = {
                        "test": "Search Functionality",
                        "status": "FAIL",
                        "http_status": response.status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "response_body": text[:200],
                        "message": f"Search failed with status {response.status}"
                    }
                    print(f"❌ {result['message']}")
                    
        except asyncio.TimeoutError:
            result = {
                "test": "Search Functionality",
                "status": "TIMEOUT",
                "message": "Search timed out after 30 seconds"
            }
            print(f"⏱️ {result['message']}")
            
        except Exception as e:
            result = {
                "test": "Search Functionality",
                "status": "ERROR",
                "error": str(e),
                "error_type": type(e).__name__,
                "message": f"Error during search test: {e}"
            }
            print(f"❌ {result['message']}")
            
        self.results.append(result)
        return result
        
    async def test_auth_status(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test authentication status endpoint"""
        print("\n🔐 Testing Authentication Status...")
        
        endpoint = f"{self.api_url}/api/auth/status"
        
        try:
            start_time = time.time()
            async with session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    auth_status = "authenticated" if data.get("authenticated") else "not authenticated"
                    result = {
                        "test": "Authentication Status",
                        "status": "PASS",
                        "http_status": response.status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "authenticated": data.get("authenticated", False),
                        "subscription": data.get("subscription", "unknown"),
                        "message": f"Auth check successful: {auth_status}"
                    }
                    print(f"✅ {result['message']} ({result['response_time_ms']}ms)")
                else:
                    text = await response.text()
                    result = {
                        "test": "Authentication Status",
                        "status": "FAIL",
                        "http_status": response.status,
                        "response_time_ms": round(response_time * 1000, 2),
                        "response_body": text[:200],
                        "message": f"Auth check failed with status {response.status}"
                    }
                    print(f"❌ {result['message']}")
                    
        except Exception as e:
            result = {
                "test": "Authentication Status",
                "status": "ERROR",
                "error": str(e),
                "error_type": type(e).__name__,
                "message": f"Error during auth check: {e}"
            }
            print(f"❌ {result['message']}")
            
        self.results.append(result)
        return result
        
    async def test_with_retries(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Test connection behavior with retries"""
        print("\n🔄 Testing Connection Resilience (3 attempts)...")
        
        endpoint = f"{self.api_url}/api/health"
        attempts = []
        
        for i in range(3):
            try:
                start_time = time.time()
                async with session.get(
                    endpoint,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    response_time = time.time() - start_time
                    
                    attempt_result = {
                        "attempt": i + 1,
                        "success": response.status == 200,
                        "status_code": response.status,
                        "response_time_ms": round(response_time * 1000, 2)
                    }
                    attempts.append(attempt_result)
                    
                    if response.status == 200:
                        print(f"  ✅ Attempt {i+1}: Success ({attempt_result['response_time_ms']}ms)")
                    else:
                        print(f"  ❌ Attempt {i+1}: HTTP {response.status}")
                        
            except Exception as e:
                attempt_result = {
                    "attempt": i + 1,
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                attempts.append(attempt_result)
                print(f"  ❌ Attempt {i+1}: {type(e).__name__}")
                
            if i < 2:  # Don't sleep after last attempt
                await asyncio.sleep(1)
                
        successful_attempts = sum(1 for a in attempts if a.get("success", False))
        result = {
            "test": "Connection Resilience",
            "status": "PASS" if successful_attempts > 0 else "FAIL",
            "successful_attempts": successful_attempts,
            "total_attempts": len(attempts),
            "attempts": attempts,
            "message": f"{successful_attempts}/{len(attempts)} attempts successful"
        }
        
        self.results.append(result)
        return result
        
    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        report = [
            "\n" + "=" * 60,
            "YouTube Music Headless Service Test Report",
            "=" * 60,
            f"Test Time: {datetime.now().isoformat()}",
            f"API URL: {self.api_url}",
            ""
        ]
        
        # Summary
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] in ["FAIL", "ERROR", "TIMEOUT"])
        
        report.append("SUMMARY:")
        report.append(f"  Total Tests: {len(self.results)}")
        report.append(f"  Passed: {passed}")
        report.append(f"  Failed: {failed}")
        report.append("")
        
        # Detailed results
        report.append("DETAILED RESULTS:")
        for result in self.results:
            report.append(f"\n{result['test']}:")
            report.append(f"  Status: {result['status']}")
            report.append(f"  Message: {result['message']}")
            
            # Add relevant details based on test type
            if "response_time_ms" in result:
                report.append(f"  Response Time: {result['response_time_ms']}ms")
            if "error" in result:
                report.append(f"  Error: {result['error']}")
            if "health_data" in result:
                report.append(f"  Health Data: {json.dumps(result['health_data'], indent=4)}")
                
        # Recommendations
        report.append("\n\nRECOMMENDATIONS:")
        
        dns_failed = any(r["test"] == "DNS Resolution" and r["status"] != "PASS" for r in self.results)
        tcp_failed = any(r["test"] == "TCP Connection" and r["status"] != "PASS" for r in self.results)
        health_failed = any(r["test"] == "Health Endpoint" and r["status"] != "PASS" for r in self.results)
        
        if dns_failed:
            report.append("  - DNS resolution failed. Check Docker network configuration.")
            report.append("    Try: docker network inspect robustty_robustty-network")
            
        if tcp_failed:
            report.append("  - TCP connection failed. Check if container is running.")
            report.append("    Try: docker ps | grep youtube-music")
            report.append("    Try: docker logs robustty-youtube-music")
            
        if health_failed:
            report.append("  - Health endpoint failed. Check container logs for errors.")
            report.append("    Try: docker logs robustty-youtube-music --tail 50")
            
        if not any([dns_failed, tcp_failed, health_failed]) and failed > 0:
            report.append("  - Service is reachable but some endpoints are failing.")
            report.append("    Check application logs and configuration.")
            
        return "\n".join(report)
        
    async def run_all_tests(self):
        """Run all connectivity tests"""
        print("🚀 Starting YouTube Music Headless Service Tests...\n")
        
        # Test DNS first (doesn't need session)
        await self.test_dns_resolution()
        
        # Test TCP connection
        await self.test_tcp_connection()
        
        # Create session for HTTP tests
        connector = aiohttp.TCPConnector(
            force_close=True,
            enable_cleanup_closed=True
        )
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # Run HTTP-based tests
            await self.test_health_endpoint(session)
            await self.test_search_functionality(session)
            await self.test_auth_status(session)
            await self.test_with_retries(session)
            
        # Generate and print report
        report = self.generate_report()
        print(report)
        
        # Save report to file
        report_file = f"youtube-music-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        with open(report_file, "w") as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_file}")
        
        # Return overall status
        return all(r["status"] == "PASS" for r in self.results)


async def main():
    # Check if custom URL provided
    api_url = "http://youtube-music-headless:9863"
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
        
    # Also test localhost alternative
    print("Testing multiple endpoints...")
    urls_to_test = [
        api_url,
        "http://localhost:9863",
        "http://127.0.0.1:9863"
    ]
    
    for url in urls_to_test:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print('='*60)
        
        tester = YouTubeMusicTester(url)
        success = await tester.run_all_tests()
        
        if success:
            print(f"\n✅ All tests passed for {url}")
            break
        else:
            print(f"\n❌ Some tests failed for {url}")
            
    return success


if __name__ == "__main__":
    exit_code = 0 if asyncio.run(main()) else 1
    sys.exit(exit_code)