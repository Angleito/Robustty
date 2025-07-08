#!/usr/bin/env python3
"""
YouTube Music Service Monitor with Fallback Detection
Monitors the YouTube Music headless service and shows fallback behavior
"""

import asyncio
import aiohttp
import time
import signal
import sys
from datetime import datetime
from typing import Dict, Any, Optional


class YouTubeMusicMonitor:
    def __init__(self):
        self.youtube_music_url = "http://youtube-music-headless:9863"
        self.monitoring = True
        self.stats = {
            "checks": 0,
            "successful": 0,
            "failed": 0,
            "consecutive_failures": 0,
            "last_success": None,
            "last_failure": None,
            "failure_reasons": {}
        }
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n📊 Final Statistics:")
        self.print_stats()
        self.monitoring = False
        sys.exit(0)
        
    async def check_youtube_music_health(self) -> Dict[str, Any]:
        """Check YouTube Music service health"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "response_time_ms": None,
            "error": None,
            "status": None
        }
        
        try:
            connector = aiohttp.TCPConnector(force_close=True)
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                start_time = time.time()
                
                async with session.get(f"{self.youtube_music_url}/api/health") as response:
                    response_time = (time.time() - start_time) * 1000
                    result["response_time_ms"] = round(response_time, 2)
                    
                    if response.status == 200:
                        data = await response.json()
                        result["success"] = True
                        result["status"] = data.get("status", "unknown")
                    else:
                        result["error"] = f"HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            result["error"] = "Timeout"
        except aiohttp.ClientConnectorError as e:
            if "Connection reset by peer" in str(e):
                result["error"] = "Connection reset by peer"
            elif "Cannot connect to host" in str(e):
                result["error"] = "Cannot connect to host"
            else:
                result["error"] = f"Connection error: {type(e).__name__}"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"
            
        return result
        
    async def check_youtube_music_search(self) -> Dict[str, Any]:
        """Test YouTube Music search functionality"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "response_time_ms": None,
            "error": None,
            "results_count": 0
        }
        
        try:
            connector = aiohttp.TCPConnector(force_close=True)
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                start_time = time.time()
                
                params = {"q": "test", "limit": 1}
                async with session.get(f"{self.youtube_music_url}/api/search", params=params) as response:
                    response_time = (time.time() - start_time) * 1000
                    result["response_time_ms"] = round(response_time, 2)
                    
                    if response.status == 200:
                        data = await response.json()
                        result["success"] = True
                        result["results_count"] = len(data.get("results", []))
                    else:
                        result["error"] = f"HTTP {response.status}"
                        
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"
            
        return result
        
    def update_stats(self, health_result: Dict[str, Any], search_result: Optional[Dict[str, Any]] = None):
        """Update monitoring statistics"""
        self.stats["checks"] += 1
        
        if health_result["success"]:
            self.stats["successful"] += 1
            self.stats["consecutive_failures"] = 0
            self.stats["last_success"] = health_result["timestamp"]
        else:
            self.stats["failed"] += 1
            self.stats["consecutive_failures"] += 1
            self.stats["last_failure"] = health_result["timestamp"]
            
            # Track failure reasons
            error = health_result.get("error", "Unknown")
            if error not in self.stats["failure_reasons"]:
                self.stats["failure_reasons"][error] = 0
            self.stats["failure_reasons"][error] += 1
            
    def print_status(self, health_result: Dict[str, Any], search_result: Optional[Dict[str, Any]] = None):
        """Print current status"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if health_result["success"]:
            health_status = f"✅ Healthy ({health_result['response_time_ms']}ms)"
        else:
            health_status = f"❌ Failed: {health_result['error']}"
            
        search_status = ""
        if search_result:
            if search_result["success"]:
                search_status = f" | Search: ✅ ({search_result['results_count']} results)"
            else:
                search_status = f" | Search: ❌ {search_result['error']}"
                
        # Print status line
        print(f"[{timestamp}] Health: {health_status}{search_status}")
        
        # Show fallback warning if consecutive failures
        if self.stats["consecutive_failures"] >= 3:
            print(f"  ⚠️  WARNING: {self.stats['consecutive_failures']} consecutive failures - bot will use fallback platforms")
            
    def print_stats(self):
        """Print accumulated statistics"""
        if self.stats["checks"] == 0:
            return
            
        success_rate = (self.stats["successful"] / self.stats["checks"]) * 100
        
        print(f"\nTotal Checks: {self.stats['checks']}")
        print(f"Successful: {self.stats['successful']} ({success_rate:.1f}%)")
        print(f"Failed: {self.stats['failed']}")
        print(f"Current Consecutive Failures: {self.stats['consecutive_failures']}")
        
        if self.stats["failure_reasons"]:
            print("\nFailure Reasons:")
            for reason, count in sorted(self.stats["failure_reasons"].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / self.stats["failed"]) * 100
                print(f"  - {reason}: {count} ({percentage:.1f}%)")
                
        if self.stats["last_success"]:
            print(f"\nLast Success: {self.stats['last_success']}")
        if self.stats["last_failure"]:
            print(f"Last Failure: {self.stats['last_failure']}")
            
    async def monitor_loop(self, interval: int = 30, include_search: bool = False):
        """Main monitoring loop"""
        print(f"🔍 Starting YouTube Music Service Monitor")
        print(f"   URL: {self.youtube_music_url}")
        print(f"   Check Interval: {interval} seconds")
        print(f"   Include Search Tests: {'Yes' if include_search else 'No'}")
        print(f"   Press Ctrl+C to stop\n")
        
        while self.monitoring:
            # Check health
            health_result = await self.check_youtube_music_health()
            
            # Optionally check search
            search_result = None
            if include_search and health_result["success"]:
                search_result = await self.check_youtube_music_search()
                
            # Update stats and print status
            self.update_stats(health_result, search_result)
            self.print_status(health_result, search_result)
            
            # Print stats every 10 checks
            if self.stats["checks"] % 10 == 0:
                print("\n--- Statistics Update ---")
                self.print_stats()
                print("--- Continuing Monitoring ---\n")
                
            # Wait for next check
            await asyncio.sleep(interval)
            
    async def run_quick_test(self):
        """Run a quick connectivity test"""
        print("🧪 Running Quick YouTube Music Connectivity Test...\n")
        
        # Test 1: Health Check
        print("1. Testing Health Endpoint...")
        health_result = await self.check_youtube_music_health()
        if health_result["success"]:
            print(f"   ✅ Success ({health_result['response_time_ms']}ms)")
        else:
            print(f"   ❌ Failed: {health_result['error']}")
            
        # Test 2: Search
        print("\n2. Testing Search Endpoint...")
        search_result = await self.check_youtube_music_search()
        if search_result["success"]:
            print(f"   ✅ Success ({search_result['response_time_ms']}ms, {search_result['results_count']} results)")
        else:
            print(f"   ❌ Failed: {search_result['error']}")
            
        # Test 3: Multiple rapid requests
        print("\n3. Testing Multiple Rapid Requests (5 health checks)...")
        rapid_results = []
        for i in range(5):
            result = await self.check_youtube_music_health()
            rapid_results.append(result)
            status = "✅" if result["success"] else "❌"
            print(f"   Request {i+1}: {status} ", end="")
            if result["success"]:
                print(f"({result['response_time_ms']}ms)")
            else:
                print(f"({result['error']})")
            await asyncio.sleep(0.5)
            
        # Summary
        successful = sum(1 for r in rapid_results if r["success"])
        print(f"\n   Summary: {successful}/5 successful")
        
        # Overall verdict
        print("\n📊 Overall Status:")
        if health_result["success"] and search_result["success"] and successful >= 4:
            print("   ✅ YouTube Music service is working properly")
        elif health_result["success"] or successful >= 3:
            print("   ⚠️  YouTube Music service is partially working (may have intermittent issues)")
        else:
            print("   ❌ YouTube Music service is not working (bot will use fallback platforms)")
            print("\n   Troubleshooting steps:")
            print("   1. Check container status: docker ps | grep youtube-music")
            print("   2. Check container logs: docker logs robustty-youtube-music --tail 50")
            print("   3. Run fix script: ./scripts/fix-youtube-music-connection.sh")
            

async def main():
    monitor = YouTubeMusicMonitor()
    
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, monitor.signal_handler)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Monitor YouTube Music service health")
    parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds (default: 30)")
    parser.add_argument("--include-search", action="store_true", help="Include search endpoint tests")
    parser.add_argument("--quick-test", action="store_true", help="Run quick test and exit")
    parser.add_argument("--url", type=str, help="Custom YouTube Music URL (default: http://youtube-music-headless:9863)")
    
    args = parser.parse_args()
    
    if args.url:
        monitor.youtube_music_url = args.url
        
    if args.quick_test:
        await monitor.run_quick_test()
    else:
        await monitor.monitor_loop(interval=args.interval, include_search=args.include_search)


if __name__ == "__main__":
    asyncio.run(main())