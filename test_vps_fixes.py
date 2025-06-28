#!/usr/bin/env python3
"""
Comprehensive VPS Fixes Validation Script
Tests all components affected by recent VPS fixes
Can be run both inside and outside Docker containers

Usage:
    # Run on host system
    python test_vps_fixes.py
    
    # Run inside Docker container
    docker-compose exec robustty python test_vps_fixes.py
    
    # Run with custom environment
    REDIS_URL=redis://localhost:6379 python test_vps_fixes.py
    
Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""

import asyncio
import os
import sys
import socket
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import aiohttp
import redis
from datetime import datetime

# Add src to path for imports when running outside container
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestResult:
    """Stores test results with status and details"""
    def __init__(self, name: str, passed: bool, details: str = "", error: str = ""):
        self.name = name
        self.passed = passed
        self.details = details
        self.error = error
        self.timestamp = datetime.now()

class VPSFixesValidator:
    """Validates all VPS fixes and configurations"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.is_docker = self._detect_docker_environment()
        self.is_vps = self._detect_vps_environment()
        
    def _detect_docker_environment(self) -> bool:
        """Detect if running inside Docker container"""
        return (
            os.path.exists('/.dockerenv') or
            os.environ.get('DOCKER_CONTAINER', '').lower() == 'true' or
            os.path.exists('/proc/1/cgroup') and 'docker' in open('/proc/1/cgroup').read()
        )
    
    def _detect_vps_environment(self) -> bool:
        """Detect if running on VPS (non-macOS environment)"""
        import platform
        system = platform.system().lower()
        
        # Check for VPS indicators
        vps_indicators = [
            system == 'linux',
            os.path.exists('/etc/vps'),
            'vps' in socket.gethostname().lower(),
            os.environ.get('VPS_DEPLOYMENT', '').lower() == 'true'
        ]
        
        return any(vps_indicators) and system != 'darwin'
    
    def add_result(self, name: str, passed: bool, details: str = "", error: str = ""):
        """Add a test result"""
        self.results.append(TestResult(name, passed, details, error))
    
    async def test_dns_resolution(self):
        """Test DNS resolution for Discord and other services"""
        print("\n🔍 Testing DNS Resolution...")
        
        dns_targets = [
            ('gateway.discord.gg', 'Discord Gateway'),
            ('discord.com', 'Discord API'),
            ('www.youtube.com', 'YouTube'),
            ('rumble.com', 'Rumble'),
            ('odysee.com', 'Odysee'),
            ('joinpeertube.org', 'PeerTube'),
            ('8.8.8.8', 'Google DNS'),
            ('1.1.1.1', 'Cloudflare DNS')
        ]
        
        for hostname, service in dns_targets:
            try:
                # Test DNS resolution
                start_time = time.time()
                result = socket.gethostbyname(hostname)
                resolution_time = (time.time() - start_time) * 1000  # ms
                
                self.add_result(
                    f"DNS: {service}",
                    True,
                    f"Resolved to {result} in {resolution_time:.1f}ms"
                )
            except socket.gaierror as e:
                self.add_result(
                    f"DNS: {service}",
                    False,
                    error=f"Failed to resolve {hostname}: {str(e)}"
                )
            except Exception as e:
                self.add_result(
                    f"DNS: {service}",
                    False,
                    error=f"Unexpected error: {str(e)}"
                )
    
    async def test_network_connectivity(self):
        """Test network connectivity to all platforms"""
        print("\n🌐 Testing Network Connectivity...")
        
        endpoints = [
            ('https://discord.com/api/v10/gateway', 'Discord API'),
            ('https://www.googleapis.com/youtube/v3/', 'YouTube API'),
            ('https://rumble.com', 'Rumble'),
            ('https://odysee.com', 'Odysee'),
            ('https://joinpeertube.org', 'PeerTube'),
            ('https://api.apify.com', 'Apify API')
        ]
        
        async with aiohttp.ClientSession() as session:
            for url, service in endpoints:
                try:
                    start_time = time.time()
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response_time = (time.time() - start_time) * 1000  # ms
                        status = response.status
                        
                        # Some APIs return 401/403 without auth, which is expected
                        passed = status < 500
                        
                        self.add_result(
                            f"Network: {service}",
                            passed,
                            f"Status {status} in {response_time:.1f}ms"
                        )
                except asyncio.TimeoutError:
                    self.add_result(
                        f"Network: {service}",
                        False,
                        error="Connection timeout (>10s)"
                    )
                except Exception as e:
                    self.add_result(
                        f"Network: {service}",
                        False,
                        error=f"Connection failed: {str(e)}"
                    )
    
    def test_cookie_system(self):
        """Test cookie system status"""
        print("\n🍪 Testing Cookie System...")
        
        # Define cookie paths to check
        cookie_paths = [
            '/app/cookies',
            '/app/data/cookies',
            './cookies',
            './data/cookies',
            os.path.expanduser('~/Library/Application Support/BraveSoftware/Brave-Browser')
        ]
        
        found_cookies = False
        cookie_files = []
        
        for path in cookie_paths:
            if os.path.exists(path):
                try:
                    # Look for cookie files
                    path_obj = Path(path)
                    txt_files = list(path_obj.glob('**/*cookies*.txt'))
                    json_files = list(path_obj.glob('**/*cookies*.json'))
                    
                    if txt_files or json_files:
                        found_cookies = True
                        cookie_files.extend([str(f) for f in txt_files + json_files])
                except Exception as e:
                    pass
        
        if found_cookies:
            self.add_result(
                "Cookie System",
                True,
                f"Found {len(cookie_files)} cookie files"
            )
            
            # Check cookie age
            for cookie_file in cookie_files[:3]:  # Check first 3 files
                try:
                    stat = os.stat(cookie_file)
                    age_hours = (time.time() - stat.st_mtime) / 3600
                    filename = os.path.basename(cookie_file)
                    
                    self.add_result(
                        f"Cookie: {filename}",
                        age_hours < 24,
                        f"Age: {age_hours:.1f} hours",
                        "" if age_hours < 24 else "Cookie file is stale (>24h old)"
                    )
                except:
                    pass
        else:
            self.add_result(
                "Cookie System",
                False,
                error="No cookie files found in any expected location"
            )
    
    def test_redis_connectivity(self):
        """Test Redis connectivity"""
        print("\n📦 Testing Redis Connectivity...")
        
        # Determine Redis URL based on environment
        redis_urls = []
        
        if self.is_docker:
            redis_urls.append('redis://redis:6379')
        
        redis_urls.extend([
            os.environ.get('REDIS_URL', ''),
            'redis://localhost:6379',
            'redis://127.0.0.1:6379'
        ])
        
        redis_connected = False
        
        for redis_url in redis_urls:
            if not redis_url:
                continue
                
            try:
                r = redis.from_url(redis_url, socket_connect_timeout=5)
                # Test connection
                r.ping()
                
                # Test write/read
                test_key = 'vps_test_key'
                test_value = f'test_{int(time.time())}'
                r.set(test_key, test_value, ex=60)
                retrieved = r.get(test_key)
                
                if retrieved and retrieved.decode() == test_value:
                    redis_connected = True
                    self.add_result(
                        "Redis Connection",
                        True,
                        f"Connected to {redis_url}"
                    )
                    
                    # Get Redis info
                    info = r.info()
                    self.add_result(
                        "Redis Status",
                        True,
                        f"Version {info.get('redis_version', 'unknown')}, "
                        f"Memory: {info.get('used_memory_human', 'unknown')}"
                    )
                    break
                    
            except Exception as e:
                continue
        
        if not redis_connected:
            self.add_result(
                "Redis Connection",
                False,
                error="Failed to connect to Redis on any URL"
            )
    
    def test_docker_network(self):
        """Test Docker network configuration"""
        print("\n🐳 Testing Docker Network...")
        
        if not self.is_docker:
            self.add_result(
                "Docker Network",
                True,
                "Not running in Docker (skipped)"
            )
            return
        
        try:
            # Check if we can resolve service names
            services = ['redis', 'robustty']
            for service in services:
                try:
                    ip = socket.gethostbyname(service)
                    self.add_result(
                        f"Docker DNS: {service}",
                        True,
                        f"Resolved to {ip}"
                    )
                except:
                    # It's okay if we can't resolve our own service name
                    if service != 'robustty':
                        self.add_result(
                            f"Docker DNS: {service}",
                            False,
                            error="Failed to resolve service name"
                        )
        except Exception as e:
            self.add_result(
                "Docker Network",
                False,
                error=f"Docker network test failed: {str(e)}"
            )
    
    def test_environment_detection(self):
        """Test environment detection"""
        print("\n🔧 Testing Environment Detection...")
        
        import platform
        
        env_info = {
            'Platform': platform.system(),
            'Release': platform.release(),
            'Machine': platform.machine(),
            'Is Docker': self.is_docker,
            'Is VPS': self.is_vps,
            'Hostname': socket.gethostname()
        }
        
        self.add_result(
            "Environment Detection",
            True,
            f"Docker: {self.is_docker}, VPS: {self.is_vps}, Platform: {platform.system()}"
        )
        
        # Check for VPS-specific optimizations
        if self.is_vps:
            self.add_result(
                "VPS Optimizations",
                True,
                "VPS environment detected - optimizations should be active"
            )
    
    async def test_voice_connection_readiness(self):
        """Test voice connection readiness"""
        print("\n🎤 Testing Voice Connection Readiness...")
        
        # Check if we can import discord.py
        try:
            import discord
            self.add_result(
                "Discord.py Import",
                True,
                f"Version {discord.__version__}"
            )
        except ImportError:
            self.add_result(
                "Discord.py Import",
                False,
                error="discord.py not installed"
            )
            return
        
        # Check for opus library
        try:
            if hasattr(discord, 'opus'):
                if discord.opus.is_loaded():
                    self.add_result(
                        "Opus Library",
                        True,
                        "Opus codec loaded successfully"
                    )
                else:
                    # Try to load opus
                    try:
                        discord.opus.load_opus('opus')
                        self.add_result(
                            "Opus Library",
                            True,
                            "Opus codec loaded after manual attempt"
                        )
                    except:
                        self.add_result(
                            "Opus Library",
                            False,
                            error="Failed to load Opus codec"
                        )
        except:
            self.add_result(
                "Opus Library",
                False,
                error="Opus check failed"
            )
        
        # Check FFmpeg
        ffmpeg_paths = ['ffmpeg', '/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg']
        ffmpeg_found = False
        
        for ffmpeg_path in ffmpeg_paths:
            try:
                result = subprocess.run(
                    [ffmpeg_path, '-version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    self.add_result(
                        "FFmpeg",
                        True,
                        f"Found at {ffmpeg_path}: {version_line}"
                    )
                    ffmpeg_found = True
                    break
            except:
                continue
        
        if not ffmpeg_found:
            self.add_result(
                "FFmpeg",
                False,
                error="FFmpeg not found in PATH"
            )
    
    def test_file_permissions(self):
        """Test file permissions for critical directories"""
        print("\n📁 Testing File Permissions...")
        
        critical_paths = [
            '/app/cookies',
            '/app/data',
            '/app/logs',
            './cookies',
            './data',
            './logs'
        ]
        
        for path in critical_paths:
            if os.path.exists(path):
                try:
                    # Test write permission
                    test_file = os.path.join(path, '.permission_test')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    
                    self.add_result(
                        f"Permissions: {path}",
                        True,
                        "Read/Write OK"
                    )
                except Exception as e:
                    self.add_result(
                        f"Permissions: {path}",
                        False,
                        error=f"No write permission: {str(e)}"
                    )
    
    async def run_all_tests(self):
        """Run all validation tests"""
        print("=" * 60)
        print("🚀 VPS Fixes Validation Script")
        print("=" * 60)
        print(f"Environment: {'Docker' if self.is_docker else 'Host'} | "
              f"{'VPS' if self.is_vps else 'Local'}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Run all tests
        await self.test_dns_resolution()
        await self.test_network_connectivity()
        self.test_cookie_system()
        self.test_redis_connectivity()
        self.test_docker_network()
        self.test_environment_detection()
        await self.test_voice_connection_readiness()
        self.test_file_permissions()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)
        
        passed = 0
        failed = 0
        
        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"\n{status} | {result.name}")
            
            if result.details:
                print(f"     Details: {result.details}")
            if result.error:
                print(f"     Error: {result.error}")
            
            if result.passed:
                passed += 1
            else:
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ({passed/len(self.results)*100:.1f}%)")
        print(f"Failed: {failed} ({failed/len(self.results)*100:.1f}%)")
        print("=" * 60)
        
        if failed > 0:
            print("\n⚠️  Some tests failed. Review the errors above.")
            print("\nCommon fixes:")
            print("- DNS issues: Check /etc/resolv.conf or Docker DNS settings")
            print("- Network issues: Check firewall rules and Docker network configuration")
            print("- Cookie issues: Run cookie extraction script or check browser data mount")
            print("- Redis issues: Ensure Redis is running and accessible")
            print("- Permission issues: Check Docker volume ownership")
        else:
            print("\n✨ All tests passed! Your VPS setup is ready.")

async def main():
    """Main entry point"""
    validator = VPSFixesValidator()
    await validator.run_all_tests()
    
    # Exit with appropriate code
    failed_count = sum(1 for r in validator.results if not r.passed)
    sys.exit(1 if failed_count > 0 else 0)

if __name__ == "__main__":
    # Handle async execution
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        sys.exit(1)