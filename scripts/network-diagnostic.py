#!/usr/bin/env python3
"""
Comprehensive Network Diagnostic Script for Robustty Bot

This script tests all critical network connectivity requirements:
1. DNS resolution for key services (Discord, YouTube, Odysee, PeerTube)
2. Connectivity to Discord gateways
3. HTTP connectivity to platform APIs including YouTube
4. Redis connectivity test with multiple configurations
5. Basic port connectivity tests

Can be run standalone to validate network connectivity fixes on VPS or local environments.
"""

import asyncio
import json
import logging
import os
import socket
import sys
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Try to import optional dependencies with fallbacks
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    print("Warning: aiohttp not available - HTTP tests will be limited")

try:
    import dns.asyncresolver
    import dns.exception
    HAS_DNS = True
except ImportError:
    HAS_DNS = False
    print("Warning: dnspython not available - DNS tests will be limited")

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    print("Warning: redis not available - Redis tests will be skipped")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NetworkDiagnostic:
    """Comprehensive network diagnostic utilities for Robustty bot"""

    def __init__(self):
        self.results = {}
        
        # DNS servers to test
        self.dns_servers = [
            ("1.1.1.1", "Cloudflare Primary"),
            ("1.0.0.1", "Cloudflare Secondary"),
            ("8.8.8.8", "Google Primary"),
            ("8.8.4.4", "Google Secondary"),
            ("9.9.9.9", "Quad9 Primary"),
        ]
        
        # Critical domains for bot functionality
        self.test_domains = [
            ("discord.com", "Discord API"),
            ("gateway.discord.gg", "Discord Gateway"),
            ("discordapp.com", "Discord CDN"),
            ("googleapis.com", "YouTube API"),
            ("youtube.com", "YouTube"),
            ("www.googleapis.com", "Google APIs"),
            ("odysee.com", "Odysee"),
            ("api.odysee.com", "Odysee API"),
            ("tube.tchncs.de", "PeerTube Instance"),
            ("framatube.org", "PeerTube Framatube"),
            ("rumble.com", "Rumble"),
        ]
        
        # HTTP endpoints to test
        self.http_endpoints = [
            ("https://discord.com/api/v10/gateway", "Discord API Gateway"),
            ("https://www.googleapis.com/youtube/v3/", "YouTube API Base"),
            ("https://api.odysee.com/", "Odysee API"),
            ("https://tube.tchncs.de/api/v1/search/videos?search=test&count=1", "PeerTube Search"),
            ("https://odysee.com/", "Odysee Main"),
            ("https://rumble.com/", "Rumble Main"),
        ]
        
        # Redis configurations to test
        self.redis_configs = [
            ("redis://localhost:6379", "Local Redis (Development)"),
            ("redis://redis:6379", "Docker Redis (VPS)"),
            ("redis://127.0.0.1:6379", "Localhost Redis"),
        ]
        
        # Port connectivity tests
        self.port_tests = [
            ("discord.com", 443, "Discord HTTPS"),
            ("gateway.discord.gg", 443, "Discord Gateway HTTPS"),
            ("googleapis.com", 443, "YouTube API HTTPS"),
            ("localhost", 6379, "Local Redis"),
        ]

    async def test_dns_resolution(self, domain: str, dns_server: str = None) -> Dict:
        """Test DNS resolution with optional specific DNS server"""
        start_time = time.time()
        
        if not HAS_DNS:
            # Fallback to socket.getaddrinfo
            try:
                result = socket.getaddrinfo(domain, None)
                addresses = [addr[4][0] for addr in result if addr[0] == socket.AF_INET]
                return {
                    "success": True,
                    "response_time": time.time() - start_time,
                    "addresses": addresses[:3],  # First 3 addresses
                    "error": None,
                    "method": "socket"
                }
            except Exception as e:
                return {
                    "success": False,
                    "response_time": time.time() - start_time,
                    "addresses": [],
                    "error": str(e),
                    "method": "socket"
                }
        
        try:
            resolver = dns.asyncresolver.Resolver()
            if dns_server:
                resolver.nameservers = [dns_server]
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answer = await resolver.resolve(domain, "A")
            response_time = time.time() - start_time
            
            return {
                "success": True,
                "response_time": response_time,
                "addresses": [str(rdata) for rdata in answer][:3],  # First 3 addresses
                "error": None,
                "method": "dns"
            }
            
        except dns.exception.Timeout:
            return {
                "success": False,
                "response_time": time.time() - start_time,
                "addresses": [],
                "error": "DNS timeout",
                "method": "dns"
            }
        except Exception as e:
            return {
                "success": False,
                "response_time": time.time() - start_time,
                "addresses": [],
                "error": str(e),
                "method": "dns"
            }

    def test_port_connectivity(self, host: str, port: int, timeout: int = 5) -> Dict:
        """Test TCP port connectivity"""
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            response_time = time.time() - start_time
            success = result == 0
            
            return {
                "success": success,
                "response_time": response_time,
                "error": None if success else f"Connection failed (code: {result})"
            }
            
        except Exception as e:
            return {
                "success": False,
                "response_time": time.time() - start_time,
                "error": str(e)
            }

    async def test_http_connectivity(self, url: str, timeout: int = 10) -> Dict:
        """Test HTTP connectivity to endpoint"""
        start_time = time.time()
        
        if not HAS_AIOHTTP:
            return {
                "success": False,
                "status_code": None,
                "response_time": 0,
                "error": "aiohttp not available"
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    response_time = time.time() - start_time
                    return {
                        "success": response.status < 400,
                        "status_code": response.status,
                        "response_time": response_time,
                        "error": None if response.status < 400 else f"HTTP {response.status}"
                    }
                    
        except asyncio.TimeoutError:
            return {
                "success": False,
                "status_code": None,
                "response_time": time.time() - start_time,
                "error": "Connection timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "response_time": time.time() - start_time,
                "error": str(e)
            }

    def test_redis_connectivity(self, redis_url: str) -> Dict:
        """Test Redis connectivity with specific URL"""
        start_time = time.time()
        
        if not HAS_REDIS:
            return {
                "success": False,
                "response_time": 0,
                "error": "redis library not available",
                "info": {}
            }
        
        try:
            # Parse URL to extract host/port for basic connectivity test
            parsed = urlparse(redis_url)
            host = parsed.hostname or 'localhost'
            port = parsed.port or 6379
            
            # First test basic TCP connectivity
            tcp_result = self.test_port_connectivity(host, port, timeout=3)
            if not tcp_result["success"]:
                return {
                    "success": False,
                    "response_time": time.time() - start_time,
                    "error": f"TCP connection failed: {tcp_result['error']}",
                    "info": {}
                }
            
            # Test Redis protocol
            r = redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
            
            # Test basic operations
            ping_result = r.ping()
            info = r.info()
            
            # Test set/get operations
            test_key = "robustty_network_test"
            test_value = f"test_{int(time.time())}"
            r.set(test_key, test_value, ex=60)  # Expire in 60 seconds
            retrieved = r.get(test_key)
            r.delete(test_key)  # Clean up
            
            response_time = time.time() - start_time
            
            return {
                "success": ping_result and retrieved == test_value,
                "response_time": response_time,
                "error": None,
                "info": {
                    "version": info.get("redis_version", "unknown"),
                    "memory_used": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "ping": ping_result,
                    "set_get_test": retrieved == test_value
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "response_time": time.time() - start_time,
                "error": str(e),
                "info": {}
            }

    async def test_youtube_api_connectivity(self) -> Dict:
        """Test YouTube API connectivity with optional API key"""
        youtube_api_key = os.getenv('YOUTUBE_API_KEY')
        
        if not youtube_api_key:
            return {
                "success": False,
                "error": "YOUTUBE_API_KEY not found in environment",
                "has_api_key": False,
                "endpoint_reachable": False
            }
        
        # Test base API endpoint
        base_url = "https://www.googleapis.com/youtube/v3/"
        base_test = await self.test_http_connectivity(base_url)
        
        if not base_test["success"]:
            return {
                "success": False,
                "error": f"YouTube API base URL unreachable: {base_test['error']}",
                "has_api_key": True,
                "endpoint_reachable": False
            }
        
        # Test actual API call
        if HAS_AIOHTTP:
            try:
                test_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&type=video&maxResults=1&key={youtube_api_key}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            data = await response.json()
                            return {
                                "success": True,
                                "error": None,
                                "has_api_key": True,
                                "endpoint_reachable": True,
                                "api_working": True,
                                "quota_remaining": response.headers.get('X-RateLimit-Remaining', 'unknown')
                            }
                        elif response.status == 403:
                            error_data = await response.json()
                            return {
                                "success": False,
                                "error": f"API key issue: {error_data.get('error', {}).get('message', 'Forbidden')}",
                                "has_api_key": True,
                                "endpoint_reachable": True,
                                "api_working": False
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"API returned HTTP {response.status}",
                                "has_api_key": True,
                                "endpoint_reachable": True,
                                "api_working": False
                            }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"API test failed: {str(e)}",
                    "has_api_key": True,
                    "endpoint_reachable": True,
                    "api_working": False
                }
        
        return {
            "success": False,
            "error": "aiohttp not available for API testing",
            "has_api_key": True,
            "endpoint_reachable": True,
            "api_working": False
        }

    async def run_dns_diagnostics(self) -> Dict:
        """Run comprehensive DNS diagnostics"""
        logger.info("Running DNS diagnostics...")
        
        dns_results = {}
        
        # Test default DNS resolution
        logger.info("Testing default DNS resolution...")
        default_results = {}
        for domain, domain_desc in self.test_domains:
            result = await self.test_dns_resolution(domain)
            default_results[domain] = result
            
            if result["success"]:
                logger.info(f"  ✓ {domain}: {result['response_time']:.3f}s -> {result['addresses'][0] if result['addresses'] else 'N/A'}")
            else:
                logger.warning(f"  ✗ {domain}: {result['error']}")
        
        dns_results["default"] = {
            "name": "System Default DNS",
            "results": default_results
        }
        
        # Test specific DNS servers if DNS library is available
        if HAS_DNS:
            for dns_server, dns_name in self.dns_servers:
                logger.info(f"Testing DNS server: {dns_name} ({dns_server})")
                server_results = {}
                
                for domain, domain_desc in self.test_domains:
                    result = await self.test_dns_resolution(domain, dns_server)
                    server_results[domain] = result
                    
                    if result["success"]:
                        logger.info(f"  ✓ {domain}: {result['response_time']:.3f}s -> {result['addresses'][0] if result['addresses'] else 'N/A'}")
                    else:
                        logger.warning(f"  ✗ {domain}: {result['error']}")
                
                dns_results[dns_server] = {
                    "name": dns_name,
                    "results": server_results
                }
        
        return dns_results

    async def run_http_diagnostics(self) -> Dict:
        """Run HTTP connectivity diagnostics"""
        logger.info("Running HTTP connectivity diagnostics...")
        
        http_results = {}
        
        for url, desc in self.http_endpoints:
            logger.info(f"Testing HTTP endpoint: {desc}")
            result = await self.test_http_connectivity(url)
            
            if result["success"]:
                logger.info(f"  ✓ {desc}: HTTP {result['status_code']} in {result['response_time']:.3f}s")
            else:
                logger.warning(f"  ✗ {desc}: {result['error']}")
            
            http_results[url] = {
                "description": desc,
                "result": result
            }
        
        return http_results

    def run_port_diagnostics(self) -> Dict:
        """Run port connectivity diagnostics"""
        logger.info("Running port connectivity diagnostics...")
        
        port_results = {}
        
        for host, port, desc in self.port_tests:
            logger.info(f"Testing port: {desc} ({host}:{port})")
            result = self.test_port_connectivity(host, port)
            
            if result["success"]:
                logger.info(f"  ✓ {desc}: Connected in {result['response_time']:.3f}s")
            else:
                logger.warning(f"  ✗ {desc}: {result['error']}")
            
            port_results[f"{host}:{port}"] = {
                "description": desc,
                "result": result
            }
        
        return port_results

    def run_redis_diagnostics(self) -> Dict:
        """Run Redis connectivity diagnostics"""
        logger.info("Running Redis connectivity diagnostics...")
        
        redis_results = {}
        
        # Test environment variable configuration
        env_redis_url = os.getenv('REDIS_URL')
        if env_redis_url:
            logger.info(f"Testing environment REDIS_URL: {env_redis_url}")
            result = self.test_redis_connectivity(env_redis_url)
            
            if result["success"]:
                logger.info(f"  ✓ Environment Redis: Connected in {result['response_time']:.3f}s")
                logger.info(f"    Version: {result['info'].get('version', 'unknown')}")
                logger.info(f"    Memory: {result['info'].get('memory_used', 'unknown')}")
            else:
                logger.warning(f"  ✗ Environment Redis: {result['error']}")
            
            redis_results["environment"] = {
                "url": env_redis_url,
                "description": "Environment REDIS_URL",
                "result": result
            }
        
        # Test standard configurations
        for redis_url, desc in self.redis_configs:
            if env_redis_url and redis_url == env_redis_url:
                continue  # Skip if already tested
                
            logger.info(f"Testing Redis config: {desc}")
            result = self.test_redis_connectivity(redis_url)
            
            if result["success"]:
                logger.info(f"  ✓ {desc}: Connected in {result['response_time']:.3f}s")
            else:
                logger.warning(f"  ✗ {desc}: {result['error']}")
            
            redis_results[redis_url] = {
                "url": redis_url,
                "description": desc,
                "result": result
            }
        
        return redis_results

    async def run_youtube_diagnostics(self) -> Dict:
        """Run YouTube API diagnostics"""
        logger.info("Running YouTube API diagnostics...")
        
        result = await self.test_youtube_api_connectivity()
        
        if result["success"]:
            logger.info("  ✓ YouTube API: Working correctly")
            if "quota_remaining" in result:
                logger.info(f"    Quota remaining: {result['quota_remaining']}")
        else:
            logger.warning(f"  ✗ YouTube API: {result['error']}")
            if not result.get("has_api_key"):
                logger.info("    Set YOUTUBE_API_KEY environment variable to test API")
        
        return {"youtube_api": result}

    def analyze_results(self, results: Dict) -> List[str]:
        """Analyze results and provide recommendations"""
        recommendations = []
        
        # Analyze DNS results
        dns_results = results.get("dns_results", {})
        working_dns_servers = []
        
        for dns_id, data in dns_results.items():
            if "results" in data:
                successful_resolutions = sum(
                    1 for result in data["results"].values() if result.get("success", False)
                )
                total_tests = len(data["results"])
                if total_tests > 0:
                    success_rate = successful_resolutions / total_tests
                    if success_rate > 0.5:  # More than 50% success
                        working_dns_servers.append((dns_id, data["name"], success_rate))
        
        if not working_dns_servers:
            recommendations.append("🚨 CRITICAL: No DNS servers are working properly")
            recommendations.append("   - Check internet connection")
            recommendations.append("   - Check firewall settings")
            recommendations.append("   - Try: sudo systemctl restart systemd-resolved")
            recommendations.append("   - Try: echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf")
        else:
            best_dns = max(working_dns_servers, key=lambda x: x[2])
            recommendations.append(f"✓ Best DNS performance: {best_dns[1]} - {best_dns[2]:.1%} success")
        
        # Analyze Discord connectivity
        discord_working = False
        for dns_id, data in dns_results.items():
            if "results" in data:
                discord_ok = data["results"].get("discord.com", {}).get("success", False)
                gateway_ok = data["results"].get("gateway.discord.gg", {}).get("success", False)
                if discord_ok and gateway_ok:
                    discord_working = True
                    break
        
        if not discord_working:
            recommendations.append("🚨 CRITICAL: Discord connectivity issues detected")
            recommendations.append("   - Bot will not be able to connect to Discord")
            recommendations.append("   - Check if Discord is blocked by firewall/ISP")
            recommendations.append("   - Try different DNS servers")
        else:
            recommendations.append("✓ Discord connectivity: Working")
        
        # Analyze YouTube API
        youtube_result = results.get("youtube_results", {}).get("youtube_api", {})
        if youtube_result.get("success"):
            recommendations.append("✓ YouTube API: Working correctly")
        elif not youtube_result.get("has_api_key"):
            recommendations.append("⚠️  YouTube API: No API key configured")
            recommendations.append("   - Set YOUTUBE_API_KEY environment variable")
            recommendations.append("   - Get API key from Google Cloud Console")
        else:
            recommendations.append(f"✗ YouTube API: {youtube_result.get('error', 'Unknown error')}")
        
        # Analyze Redis connectivity
        redis_results = results.get("redis_results", {})
        redis_working = any(
            data.get("result", {}).get("success", False)
            for data in redis_results.values()
        )
        
        if redis_working:
            recommendations.append("✓ Redis connectivity: Working")
        else:
            recommendations.append("🚨 CRITICAL: Redis connectivity failed")
            recommendations.append("   - Bot will not function without Redis")
            recommendations.append("   - Check if Redis is running: docker-compose ps")
            recommendations.append("   - Check Redis logs: docker-compose logs redis")
            recommendations.append("   - Try: docker-compose restart redis")
        
        # Analyze HTTP connectivity
        http_results = results.get("http_results", {})
        failed_platforms = [
            data["description"] for data in http_results.values()
            if not data.get("result", {}).get("success", False)
        ]
        
        if failed_platforms:
            recommendations.append("⚠️  Some platforms unreachable:")
            for platform in failed_platforms:
                recommendations.append(f"   - {platform}")
            recommendations.append("   - Bot will use fallback mechanisms")
        
        # General network health
        if len(working_dns_servers) < 2:
            recommendations.append("💡 Consider configuring backup DNS servers")
        
        return recommendations

    async def run_full_diagnostic(self) -> Dict:
        """Run complete network diagnostic"""
        logger.info("Starting comprehensive network diagnostic for Robustty bot...")
        
        results = {}
        
        # Run all diagnostics
        results["dns_results"] = await self.run_dns_diagnostics()
        results["http_results"] = await self.run_http_diagnostics()
        results["port_results"] = self.run_port_diagnostics()
        results["redis_results"] = self.run_redis_diagnostics()
        results["youtube_results"] = await self.run_youtube_diagnostics()
        
        # Analyze and provide recommendations
        results["recommendations"] = self.analyze_results(results)
        results["timestamp"] = time.time()
        
        return results

    def print_summary(self, results: Dict):
        """Print comprehensive diagnostic summary"""
        print("\n" + "="*70)
        print("ROBUSTTY BOT NETWORK CONNECTIVITY DIAGNOSTIC SUMMARY")
        print("="*70)
        
        # Critical status check
        critical_issues = [rec for rec in results["recommendations"] if "🚨 CRITICAL" in rec]
        if critical_issues:
            print("\n🚨 CRITICAL ISSUES DETECTED:")
            for issue in critical_issues:
                print(f"  {issue}")
        
        print("\n📋 ALL RECOMMENDATIONS:")
        for rec in results["recommendations"]:
            print(f"  {rec}")
        
        print(f"\n📊 DETAILED TEST RESULTS:")
        
        # DNS Summary
        dns_results = results.get("dns_results", {})
        working_dns = sum(
            1 for data in dns_results.values()
            if "results" in data and 
            sum(1 for r in data["results"].values() if r.get("success")) > len(data["results"]) * 0.5
        )
        print(f"   DNS Servers Working: {working_dns}/{len(dns_results)}")
        
        # HTTP Summary
        http_results = results.get("http_results", {})
        working_http = sum(
            1 for data in http_results.values()
            if data.get("result", {}).get("success", False)
        )
        print(f"   HTTP Endpoints Working: {working_http}/{len(http_results)}")
        
        # Port Summary
        port_results = results.get("port_results", {})
        working_ports = sum(
            1 for data in port_results.values()
            if data.get("result", {}).get("success", False)
        )
        print(f"   Port Tests Passing: {working_ports}/{len(port_results)}")
        
        # Redis Summary
        redis_results = results.get("redis_results", {})
        working_redis = sum(
            1 for data in redis_results.values()
            if data.get("result", {}).get("success", False)
        )
        print(f"   Redis Configurations Working: {working_redis}/{len(redis_results)}")
        
        # YouTube Summary
        youtube_results = results.get("youtube_results", {})
        youtube_api = youtube_results.get("youtube_api", {})
        youtube_status = "✓ Working" if youtube_api.get("success") else "✗ Issues"
        print(f"   YouTube API Status: {youtube_status}")
        
        print("\n💡 NEXT STEPS:")
        if critical_issues:
            print("   1. Fix critical issues above before running the bot")
            print("   2. Re-run this diagnostic after making changes")
            print("   3. Check bot logs for additional error details")
        else:
            print("   1. Network connectivity looks good!")
            print("   2. Start the bot with: docker-compose up -d")
            print("   3. Monitor logs with: docker-compose logs -f robustty")
        
        print("\n" + "="*70)


def check_dependencies():
    """Check and report on required dependencies"""
    print("Checking diagnostic dependencies...")
    
    missing = []
    if not HAS_AIOHTTP:
        missing.append("aiohttp (pip install aiohttp)")
    if not HAS_DNS:
        missing.append("dnspython (pip install dnspython)")
    if not HAS_REDIS:
        missing.append("redis (pip install redis)")
    
    if missing:
        print("⚠️  Some optional dependencies are missing:")
        for dep in missing:
            print(f"   - {dep}")
        print("   Run: pip install aiohttp dnspython redis")
        print("   Some tests will be limited without these dependencies.\n")
    else:
        print("✓ All dependencies available\n")


async def main():
    """Main diagnostic function"""
    print("Robustty Bot Network Diagnostic Tool")
    print("====================================")
    
    check_dependencies()
    
    diagnostic = NetworkDiagnostic()
    
    try:
        results = await diagnostic.run_full_diagnostic()
        diagnostic.print_summary(results)
        
        # Save results to file
        results_file = "/tmp/robustty_network_diagnostic.json"
        try:
            with open(results_file, 'w') as f:
                # Convert results to JSON-serializable format
                json_results = json.loads(json.dumps(results, default=str))
                json.dump(json_results, f, indent=2)
            print(f"\n📄 Detailed results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save results file: {e}")
        
        # Exit with appropriate code
        critical_issues = [rec for rec in results["recommendations"] if "🚨 CRITICAL" in rec]
        if critical_issues:
            logger.error("Critical network issues detected - bot will not function properly!")
            sys.exit(1)
        else:
            logger.info("Network diagnostic completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Diagnostic failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())