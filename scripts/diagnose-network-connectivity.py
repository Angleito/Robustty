#!/usr/bin/env python3
"""
Network connectivity diagnostic script for Robustty bot.

This script diagnoses common network connectivity issues and provides
recommendations for fixes.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, List, Optional

import aiohttp
import dns.asyncresolver
import dns.exception

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NetworkDiagnostic:
    """Network diagnostic utilities"""

    def __init__(self):
        self.results = {}
        
        # Test endpoints
        self.dns_servers = [
            ("1.1.1.1", "Cloudflare Primary"),
            ("8.8.8.8", "Google Primary"),
            ("9.9.9.9", "Quad9 Primary"),
        ]
        
        self.test_domains = [
            ("discord.com", "Discord API"),
            ("gateway.discord.gg", "Discord Gateway"),
            ("api.lbry.tv", "Odysee API"),
            ("tube.tchncs.de", "PeerTube Instance"),
            ("framatube.org", "PeerTube Framatube"),
        ]
        
        self.http_endpoints = [
            ("https://discord.com/api/v10/gateway", "Discord API Gateway"),
            ("https://api.lbry.tv", "Odysee API"),
            ("https://tube.tchncs.de/api/v1/search/videos?search=test&count=1", "PeerTube Search"),
        ]

    async def test_dns_resolution(self, domain: str, dns_server: str) -> Dict:
        """Test DNS resolution with specific DNS server"""
        start_time = time.time()
        
        try:
            resolver = dns.asyncresolver.Resolver()
            resolver.nameservers = [dns_server]
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answer = await resolver.resolve(domain, "A")
            response_time = time.time() - start_time
            
            return {
                "success": True,
                "response_time": response_time,
                "addresses": [str(rdata) for rdata in answer],
                "error": None
            }
            
        except dns.exception.Timeout:
            return {
                "success": False,
                "response_time": time.time() - start_time,
                "addresses": [],
                "error": "DNS timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "response_time": time.time() - start_time,
                "addresses": [],
                "error": str(e)
            }

    async def test_http_connectivity(self, url: str, timeout: int = 10) -> Dict:
        """Test HTTP connectivity to endpoint"""
        start_time = time.time()
        
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

    async def run_dns_diagnostics(self) -> Dict:
        """Run comprehensive DNS diagnostics"""
        logger.info("Running DNS diagnostics...")
        
        dns_results = {}
        
        for dns_server, dns_name in self.dns_servers:
            logger.info(f"Testing DNS server: {dns_name} ({dns_server})")
            server_results = {}
            
            for domain, domain_desc in self.test_domains:
                result = await self.test_dns_resolution(domain, dns_server)
                server_results[domain] = result
                
                if result["success"]:
                    logger.info(f"  ✓ {domain}: {result['response_time']:.3f}s -> {result['addresses'][0]}")
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

    def analyze_results(self, dns_results: Dict, http_results: Dict) -> List[str]:
        """Analyze results and provide recommendations"""
        recommendations = []
        
        # Check DNS servers
        working_dns_servers = []
        for dns_server, data in dns_results.items():
            successful_resolutions = sum(
                1 for result in data["results"].values() if result["success"]
            )
            total_tests = len(data["results"])
            success_rate = successful_resolutions / total_tests
            
            if success_rate > 0.5:  # More than 50% success
                working_dns_servers.append((dns_server, data["name"], success_rate))
        
        if not working_dns_servers:
            recommendations.append("🚨 CRITICAL: No DNS servers are working properly")
            recommendations.append("   - Check internet connection")
            recommendations.append("   - Check firewall settings")
            recommendations.append("   - Contact network administrator")
        else:
            best_dns = max(working_dns_servers, key=lambda x: x[2])
            recommendations.append(f"✓ Best DNS server: {best_dns[1]} ({best_dns[0]}) - {best_dns[2]:.1%} success")
        
        # Check Discord connectivity
        discord_issues = []
        for dns_server, data in dns_results.items():
            discord_results = data["results"].get("discord.com", {})
            gateway_results = data["results"].get("gateway.discord.gg", {})
            
            if not discord_results.get("success"):
                discord_issues.append(f"Discord.com resolution failed with {data['name']}")
            if not gateway_results.get("success"):
                discord_issues.append(f"Discord gateway resolution failed with {data['name']}")
        
        if discord_issues:
            recommendations.append("⚠️  Discord connectivity issues detected:")
            for issue in discord_issues:
                recommendations.append(f"   - {issue}")
            recommendations.append("   - Try using alternative DNS servers")
            recommendations.append("   - Check if Discord is blocked by ISP/firewall")
        
        # Check platform connectivity
        platform_issues = []
        failed_http_tests = [
            desc for url, data in http_results.items() 
            if not data["result"]["success"]
        ]
        
        if failed_http_tests:
            recommendations.append("⚠️  Platform connectivity issues:")
            for desc in failed_http_tests:
                recommendations.append(f"   - {desc['description']} failed")
            recommendations.append("   - These platforms may be unavailable or blocked")
            recommendations.append("   - Bot will use fallback mechanisms")
        
        # General recommendations
        if len(working_dns_servers) < 2:
            recommendations.append("💡 Consider configuring alternative DNS servers")
        
        return recommendations

    async def run_full_diagnostic(self) -> Dict:
        """Run complete network diagnostic"""
        logger.info("Starting comprehensive network diagnostic...")
        
        # Run diagnostics
        dns_results = await self.run_dns_diagnostics()
        http_results = await self.run_http_diagnostics()
        
        # Analyze and provide recommendations
        recommendations = self.analyze_results(dns_results, http_results)
        
        return {
            "dns_results": dns_results,
            "http_results": http_results,
            "recommendations": recommendations,
            "timestamp": time.time()
        }

    def print_summary(self, results: Dict):
        """Print diagnostic summary"""
        print("\n" + "="*60)
        print("NETWORK CONNECTIVITY DIAGNOSTIC SUMMARY")
        print("="*60)
        
        print("\n📋 RECOMMENDATIONS:")
        for rec in results["recommendations"]:
            print(f"  {rec}")
        
        print(f"\n📊 DETAILED RESULTS:")
        print(f"   DNS Servers Tested: {len(results['dns_results'])}")
        print(f"   HTTP Endpoints Tested: {len(results['http_results'])}")
        
        # DNS Summary
        working_dns = 0
        for dns_server, data in results["dns_results"].items():
            successful = sum(1 for r in data["results"].values() if r["success"])
            total = len(data["results"])
            if successful > total * 0.5:
                working_dns += 1
        
        print(f"   Working DNS Servers: {working_dns}/{len(results['dns_results'])}")
        
        # HTTP Summary
        working_http = sum(
            1 for data in results["http_results"].values() 
            if data["result"]["success"]
        )
        print(f"   Working HTTP Endpoints: {working_http}/{len(results['http_results'])}")
        
        print("\n" + "="*60)


async def main():
    """Main diagnostic function"""
    diagnostic = NetworkDiagnostic()
    
    try:
        results = await diagnostic.run_full_diagnostic()
        diagnostic.print_summary(results)
        
        # Exit with appropriate code
        failed_critical = any(
            "CRITICAL" in rec for rec in results["recommendations"]
        )
        
        if failed_critical:
            logger.error("Critical network issues detected!")
            sys.exit(1)
        else:
            logger.info("Network diagnostic completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Diagnostic failed with error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())