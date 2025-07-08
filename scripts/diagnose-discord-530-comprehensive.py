#!/usr/bin/env python3
"""
Comprehensive Discord WebSocket 530 Diagnostic Tool
Performs deep investigation of authentication failures with 5 specialized modules.
"""

import asyncio
import json
import os
import sys
import time
import subprocess
import socket
import aiohttp
import requests
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import psutil
import re
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DiscordAuthDiagnostics:
    """Comprehensive diagnostics for Discord WebSocket 530 errors."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "modules": {},
            "summary": {},
            "recommendations": []
        }
        self.token = os.getenv("DISCORD_TOKEN", "").strip()
        self.bot_id = None
        
    async def run_all_diagnostics(self) -> Dict[str, Any]:
        """Run all diagnostic modules and compile results."""
        print("\n🔍 Discord WebSocket 530 Comprehensive Diagnostics")
        print("=" * 60)
        
        # Module 1: Bot Application Status
        print("\n📱 Module 1: Bot Application Status Check")
        await self.check_bot_application_status()
        
        # Module 2: Environment & Network Analysis
        print("\n🌐 Module 2: Environment & Network Analysis")
        await self.analyze_environment_network()
        
        # Module 3: Instance & Session Detection
        print("\n🔄 Module 3: Instance & Session Detection")
        await self.detect_multiple_instances()
        
        # Module 4: Rate Limiting & IP Investigation
        print("\n⏱️ Module 4: Rate Limiting & IP Investigation")
        await self.investigate_rate_limiting()
        
        # Module 5: Code & Configuration Audit
        print("\n⚙️ Module 5: Code & Configuration Audit")
        await self.audit_code_configuration()
        
        # Generate summary and recommendations
        self.generate_summary_recommendations()
        
        return self.results
    
    async def check_bot_application_status(self):
        """Module 1: Check bot application status via Discord API."""
        module_results = {
            "token_validation": {},
            "bot_info": {},
            "application_info": {},
            "gateway_info": {},
            "errors": []
        }
        
        # Validate token format
        print("  • Validating token format...")
        if not self.token:
            module_results["token_validation"]["status"] = "missing"
            module_results["errors"].append("DISCORD_TOKEN environment variable not set")
        elif not re.match(r'^[A-Za-z0-9_\-\.]+$', self.token):
            module_results["token_validation"]["status"] = "invalid_format"
            module_results["errors"].append("Token contains invalid characters")
        else:
            module_results["token_validation"]["status"] = "valid_format"
            module_results["token_validation"]["length"] = len(self.token)
            module_results["token_validation"]["prefix"] = self.token[:10] + "..."
            
        # Check bot user info
        if self.token:
            print("  • Fetching bot user information...")
            headers = {"Authorization": f"Bot {self.token}"}
            
            try:
                # Get bot user
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://discord.com/api/v10/users/@me",
                        headers=headers
                    ) as resp:
                        if resp.status == 200:
                            bot_data = await resp.json()
                            self.bot_id = bot_data.get("id")
                            module_results["bot_info"] = {
                                "id": bot_data.get("id"),
                                "username": bot_data.get("username"),
                                "discriminator": bot_data.get("discriminator"),
                                "verified": bot_data.get("verified", False),
                                "mfa_enabled": bot_data.get("mfa_enabled", False),
                                "bot": bot_data.get("bot", False),
                                "system": bot_data.get("system", False),
                                "flags": bot_data.get("flags", 0)
                            }
                            print(f"    ✓ Bot: {bot_data.get('username')}#{bot_data.get('discriminator')}")
                        elif resp.status == 401:
                            module_results["errors"].append("Invalid token - authentication failed")
                            print("    ✗ Invalid token")
                        else:
                            module_results["errors"].append(f"API error: {resp.status}")
                            print(f"    ✗ API error: {resp.status}")
                    
                    # Get application info
                    if self.bot_id:
                        print("  • Fetching application information...")
                        async with session.get(
                            "https://discord.com/api/v10/oauth2/applications/@me",
                            headers=headers
                        ) as resp:
                            if resp.status == 200:
                                app_data = await resp.json()
                                module_results["application_info"] = {
                                    "id": app_data.get("id"),
                                    "name": app_data.get("name"),
                                    "owner_id": app_data.get("owner", {}).get("id"),
                                    "team_id": app_data.get("team", {}).get("id") if app_data.get("team") else None,
                                    "public": app_data.get("bot_public", True),
                                    "require_code_grant": app_data.get("bot_require_code_grant", False),
                                    "verify_key": bool(app_data.get("verify_key"))
                                }
                                print(f"    ✓ Application: {app_data.get('name')}")
                    
                    # Get gateway info
                    print("  • Fetching gateway information...")
                    async with session.get(
                        "https://discord.com/api/v10/gateway/bot",
                        headers=headers
                    ) as resp:
                        if resp.status == 200:
                            gateway_data = await resp.json()
                            module_results["gateway_info"] = {
                                "url": gateway_data.get("url"),
                                "shards": gateway_data.get("shards", 1),
                                "session_start_limit": gateway_data.get("session_start_limit", {})
                            }
                            limits = gateway_data.get("session_start_limit", {})
                            print(f"    ✓ Gateway: {limits.get('remaining', 0)}/{limits.get('total', 0)} sessions remaining")
                        else:
                            module_results["errors"].append(f"Gateway API error: {resp.status}")
                            
            except Exception as e:
                module_results["errors"].append(f"API request failed: {str(e)}")
                print(f"    ✗ API request failed: {e}")
        
        self.results["modules"]["bot_status"] = module_results
    
    async def analyze_environment_network(self):
        """Module 2: Analyze environment and network configuration."""
        module_results = {
            "environment": {},
            "network": {},
            "dns": {},
            "connectivity": {},
            "errors": []
        }
        
        # Check environment
        print("  • Analyzing environment...")
        module_results["environment"] = {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "is_docker": os.path.exists("/.dockerenv"),
            "is_vps": os.getenv("VOICE_ENVIRONMENT") == "vps",
            "hostname": socket.gethostname(),
            "user": os.getenv("USER", "unknown"),
            "pwd": os.getcwd()
        }
        
        # Check network interfaces
        print("  • Checking network interfaces...")
        try:
            interfaces = psutil.net_if_addrs()
            module_results["network"]["interfaces"] = []
            for iface, addrs in interfaces.items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        module_results["network"]["interfaces"].append({
                            "name": iface,
                            "ip": addr.address,
                            "netmask": addr.netmask
                        })
        except Exception as e:
            module_results["errors"].append(f"Network interface check failed: {str(e)}")
        
        # Check DNS resolution
        print("  • Testing DNS resolution...")
        dns_tests = [
            ("discord.com", "Discord main"),
            ("gateway.discord.gg", "Discord gateway"),
            ("8.8.8.8", "Google DNS")
        ]
        
        module_results["dns"]["results"] = []
        for host, desc in dns_tests:
            try:
                start = time.time()
                ip = socket.gethostbyname(host)
                duration = (time.time() - start) * 1000
                module_results["dns"]["results"].append({
                    "host": host,
                    "description": desc,
                    "resolved_ip": ip,
                    "duration_ms": round(duration, 2),
                    "success": True
                })
                print(f"    ✓ {desc}: {ip} ({duration:.0f}ms)")
            except Exception as e:
                module_results["dns"]["results"].append({
                    "host": host,
                    "description": desc,
                    "error": str(e),
                    "success": False
                })
                print(f"    ✗ {desc}: Failed - {e}")
        
        # Test connectivity to Discord
        print("  • Testing Discord connectivity...")
        connectivity_tests = [
            ("https://discord.com/api/v10/gateway", "API Gateway"),
            ("wss://gateway.discord.gg", "WebSocket Gateway"),
            ("https://cdn.discordapp.com", "CDN")
        ]
        
        module_results["connectivity"]["tests"] = []
        for url, desc in connectivity_tests:
            try:
                if url.startswith("wss://"):
                    # WebSocket test
                    import websockets
                    async with websockets.connect(url, timeout=5) as ws:
                        module_results["connectivity"]["tests"].append({
                            "url": url,
                            "description": desc,
                            "protocol": "websocket",
                            "success": True
                        })
                        print(f"    ✓ {desc}: Connected")
                else:
                    # HTTP test
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=5) as resp:
                            module_results["connectivity"]["tests"].append({
                                "url": url,
                                "description": desc,
                                "protocol": "https",
                                "status_code": resp.status,
                                "success": resp.status < 400
                            })
                            print(f"    ✓ {desc}: {resp.status}")
            except Exception as e:
                module_results["connectivity"]["tests"].append({
                    "url": url,
                    "description": desc,
                    "error": str(e),
                    "success": False
                })
                print(f"    ✗ {desc}: {type(e).__name__}")
        
        self.results["modules"]["environment_network"] = module_results
    
    async def detect_multiple_instances(self):
        """Module 3: Detect multiple bot instances and session conflicts."""
        module_results = {
            "processes": {},
            "containers": {},
            "sessions": {},
            "port_usage": {},
            "errors": []
        }
        
        # Check for multiple Python processes
        print("  • Checking for multiple bot processes...")
        try:
            current_pid = os.getpid()
            bot_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    info = proc.info
                    if info['name'] in ['python', 'python3']:
                        cmdline = ' '.join(info['cmdline'] or [])
                        if 'robustty' in cmdline.lower() or 'main.py' in cmdline:
                            bot_processes.append({
                                "pid": info['pid'],
                                "is_current": info['pid'] == current_pid,
                                "cmdline": cmdline[:100] + "..." if len(cmdline) > 100 else cmdline,
                                "uptime_seconds": int(time.time() - info['create_time'])
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            module_results["processes"]["bot_instances"] = bot_processes
            module_results["processes"]["count"] = len(bot_processes)
            
            if len(bot_processes) > 1:
                print(f"    ⚠️ Found {len(bot_processes)} bot processes!")
            else:
                print(f"    ✓ Single bot process found")
                
        except Exception as e:
            module_results["errors"].append(f"Process detection failed: {str(e)}")
        
        # Check Docker containers
        print("  • Checking Docker containers...")
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container = json.loads(line)
                        if 'robustty' in container.get('Names', '').lower():
                            containers.append({
                                "id": container.get('ID', '')[:12],
                                "name": container.get('Names', ''),
                                "status": container.get('Status', ''),
                                "ports": container.get('Ports', '')
                            })
                
                module_results["containers"]["instances"] = containers
                module_results["containers"]["count"] = len(containers)
                
                if len(containers) > 1:
                    print(f"    ⚠️ Found {len(containers)} bot containers!")
                else:
                    print(f"    ✓ {len(containers)} bot container(s) found")
            else:
                module_results["containers"]["error"] = "Docker not available"
                
        except Exception as e:
            module_results["containers"]["error"] = str(e)
        
        # Check for session files or locks
        print("  • Checking for session artifacts...")
        session_paths = [
            Path("data/session.json"),
            Path("data/.lock"),
            Path("/tmp/robustty.lock"),
            Path("/var/lock/robustty.lock")
        ]
        
        module_results["sessions"]["artifacts"] = []
        for path in session_paths:
            if path.exists():
                stat = path.stat()
                module_results["sessions"]["artifacts"].append({
                    "path": str(path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "age_seconds": int(time.time() - stat.st_mtime)
                })
                print(f"    ⚠️ Found session artifact: {path}")
        
        # Check port usage
        print("  • Checking port usage...")
        try:
            connections = psutil.net_connections()
            voice_ports = []
            
            for conn in connections:
                if conn.status == 'LISTEN' and 50000 <= conn.laddr.port <= 50100:
                    voice_ports.append({
                        "port": conn.laddr.port,
                        "pid": conn.pid,
                        "status": conn.status
                    })
            
            module_results["port_usage"]["voice_ports"] = voice_ports
            module_results["port_usage"]["count"] = len(voice_ports)
            
        except Exception as e:
            module_results["errors"].append(f"Port check failed: {str(e)}")
        
        self.results["modules"]["instance_detection"] = module_results
    
    async def investigate_rate_limiting(self):
        """Module 4: Investigate rate limiting and IP blocking."""
        module_results = {
            "ip_info": {},
            "rate_limit_status": {},
            "cloudflare_check": {},
            "timing_analysis": {},
            "errors": []
        }
        
        # Get external IP
        print("  • Fetching external IP information...")
        try:
            async with aiohttp.ClientSession() as session:
                # Get IP info
                async with session.get("https://ipinfo.io/json", timeout=5) as resp:
                    if resp.status == 200:
                        ip_data = await resp.json()
                        module_results["ip_info"] = {
                            "ip": ip_data.get("ip"),
                            "city": ip_data.get("city"),
                            "region": ip_data.get("region"),
                            "country": ip_data.get("country"),
                            "org": ip_data.get("org"),
                            "hostname": ip_data.get("hostname", "N/A")
                        }
                        print(f"    ✓ IP: {ip_data.get('ip')} ({ip_data.get('org')})")
                        
                        # Check if IP is from known VPS/cloud providers
                        org = ip_data.get("org", "").lower()
                        known_providers = ["digitalocean", "aws", "google", "azure", "linode", "vultr", "ovh"]
                        is_vps = any(provider in org for provider in known_providers)
                        module_results["ip_info"]["is_vps_ip"] = is_vps
                        
                        if is_vps:
                            print(f"    ⚠️ VPS/Cloud IP detected - may face stricter rate limits")
                            
        except Exception as e:
            module_results["errors"].append(f"IP lookup failed: {str(e)}")
        
        # Test rate limit headers
        print("  • Testing Discord rate limit status...")
        if self.token:
            headers = {"Authorization": f"Bot {self.token}"}
            
            try:
                async with aiohttp.ClientSession() as session:
                    # Make a simple API call to check rate limit headers
                    async with session.get(
                        "https://discord.com/api/v10/users/@me",
                        headers=headers
                    ) as resp:
                        rate_limit_headers = {
                            "limit": resp.headers.get("X-RateLimit-Limit"),
                            "remaining": resp.headers.get("X-RateLimit-Remaining"),
                            "reset": resp.headers.get("X-RateLimit-Reset"),
                            "reset_after": resp.headers.get("X-RateLimit-Reset-After"),
                            "bucket": resp.headers.get("X-RateLimit-Bucket"),
                            "global": resp.headers.get("X-RateLimit-Global"),
                            "scope": resp.headers.get("X-RateLimit-Scope")
                        }
                        
                        module_results["rate_limit_status"]["headers"] = rate_limit_headers
                        
                        if rate_limit_headers["remaining"]:
                            print(f"    ✓ Rate limit: {rate_limit_headers['remaining']}/{rate_limit_headers['limit']} remaining")
                        
                        # Check for rate limit response
                        if resp.status == 429:
                            retry_after = resp.headers.get("Retry-After", "unknown")
                            module_results["rate_limit_status"]["rate_limited"] = True
                            module_results["rate_limit_status"]["retry_after"] = retry_after
                            print(f"    ✗ Rate limited! Retry after: {retry_after}s")
                            
            except Exception as e:
                module_results["errors"].append(f"Rate limit check failed: {str(e)}")
        
        # Check Cloudflare challenge
        print("  • Checking for Cloudflare challenges...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://discord.com", timeout=5) as resp:
                    cf_headers = {
                        "cf_ray": resp.headers.get("CF-Ray"),
                        "cf_cache_status": resp.headers.get("CF-Cache-Status"),
                        "server": resp.headers.get("Server", "")
                    }
                    
                    module_results["cloudflare_check"]["headers"] = cf_headers
                    module_results["cloudflare_check"]["uses_cloudflare"] = bool(cf_headers["cf_ray"])
                    
                    # Check for challenge page
                    text = await resp.text()
                    if "Checking your browser" in text or resp.status == 503:
                        module_results["cloudflare_check"]["challenge_detected"] = True
                        print("    ⚠️ Cloudflare challenge detected!")
                    else:
                        module_results["cloudflare_check"]["challenge_detected"] = False
                        print("    ✓ No Cloudflare challenge")
                        
        except Exception as e:
            module_results["errors"].append(f"Cloudflare check failed: {str(e)}")
        
        # Timing analysis
        print("  • Performing connection timing analysis...")
        timings = []
        
        for i in range(3):
            try:
                start = time.time()
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://discord.com/api/v10/gateway",
                        timeout=10
                    ) as resp:
                        duration = (time.time() - start) * 1000
                        timings.append({
                            "attempt": i + 1,
                            "duration_ms": round(duration, 2),
                            "status": resp.status
                        })
                        
                await asyncio.sleep(1)  # Small delay between attempts
                
            except Exception as e:
                timings.append({
                    "attempt": i + 1,
                    "error": str(e)
                })
        
        module_results["timing_analysis"]["attempts"] = timings
        avg_time = sum(t.get("duration_ms", 0) for t in timings if "duration_ms" in t) / len([t for t in timings if "duration_ms" in t])
        module_results["timing_analysis"]["average_ms"] = round(avg_time, 2) if avg_time else None
        
        if avg_time and avg_time > 1000:
            print(f"    ⚠️ High latency detected: {avg_time:.0f}ms average")
        elif avg_time:
            print(f"    ✓ Normal latency: {avg_time:.0f}ms average")
        
        self.results["modules"]["rate_limiting"] = module_results
    
    async def audit_code_configuration(self):
        """Module 5: Audit code configuration and intent settings."""
        module_results = {
            "intent_analysis": {},
            "discord_py_version": {},
            "token_usage": {},
            "connection_settings": {},
            "errors": []
        }
        
        # Check discord.py version
        print("  • Checking discord.py installation...")
        try:
            import discord
            module_results["discord_py_version"] = {
                "version": discord.__version__,
                "location": discord.__file__,
                "voice_support": hasattr(discord, 'VoiceClient')
            }
            print(f"    ✓ discord.py version: {discord.__version__}")
            
            # Check version compatibility
            major, minor = map(int, discord.__version__.split('.')[:2])
            if major < 2:
                module_results["discord_py_version"]["outdated"] = True
                print("    ⚠️ discord.py version is outdated (< 2.0)")
                
        except ImportError:
            module_results["errors"].append("discord.py not installed")
            print("    ✗ discord.py not found")
        
        # Analyze bot intents
        print("  • Analyzing bot intent configuration...")
        bot_file = Path("src/bot/bot.py")
        if bot_file.exists():
            content = bot_file.read_text()
            
            # Search for intent configuration
            intent_patterns = {
                "discord.Intents.default()": "default",
                "discord.Intents.all()": "all",
                "discord.Intents(": "custom",
                ".message_content": "message_content",
                ".guilds": "guilds",
                ".voice_states": "voice_states",
                ".members": "members",
                ".presences": "presences"
            }
            
            found_intents = []
            for pattern, intent_type in intent_patterns.items():
                if pattern in content:
                    found_intents.append(intent_type)
            
            module_results["intent_analysis"]["found_intents"] = found_intents
            module_results["intent_analysis"]["has_message_content"] = "message_content" in found_intents
            module_results["intent_analysis"]["has_voice_states"] = "voice_states" in found_intents
            
            # Check for privileged intents
            privileged = ["members", "presences", "message_content"]
            found_privileged = [i for i in found_intents if i in privileged]
            module_results["intent_analysis"]["privileged_intents"] = found_privileged
            
            if found_privileged:
                print(f"    ⚠️ Privileged intents detected: {', '.join(found_privileged)}")
                print("       Make sure these are enabled in Discord Developer Portal!")
            
            if not module_results["intent_analysis"]["has_voice_states"]:
                print("    ⚠️ voice_states intent may be missing!")
                
        else:
            module_results["errors"].append("Bot file not found")
        
        # Check token usage in code
        print("  • Auditing token usage patterns...")
        src_dir = Path("src")
        token_usage_files = []
        
        if src_dir.exists():
            for py_file in src_dir.rglob("*.py"):
                try:
                    content = py_file.read_text()
                    if "DISCORD_TOKEN" in content or ".run(" in content or "client.start(" in content:
                        # Count occurrences
                        token_refs = content.count("DISCORD_TOKEN")
                        run_calls = content.count(".run(") + content.count(".start(")
                        
                        token_usage_files.append({
                            "file": str(py_file.relative_to(Path.cwd())),
                            "token_references": token_refs,
                            "run_calls": run_calls
                        })
                except Exception:
                    pass
            
            module_results["token_usage"]["files"] = token_usage_files
            module_results["token_usage"]["total_files"] = len(token_usage_files)
            
            # Check for multiple run calls
            total_run_calls = sum(f["run_calls"] for f in token_usage_files)
            if total_run_calls > 1:
                print(f"    ⚠️ Multiple bot.run() calls detected ({total_run_calls} total)")
        
        # Check connection settings
        print("  • Checking connection settings...")
        config_checks = {
            "reconnect": "reconnect=",
            "ws_trace": "enable_debug_events=",
            "compression": "compress=",
            "chunk_guilds": "chunk_guilds_at_startup=",
            "shard_count": "shard_count=",
            "member_cache": "MemberCacheFlags",
            "max_messages": "max_messages="
        }
        
        found_settings = []
        for py_file in src_dir.rglob("*.py"):
            try:
                content = py_file.read_text()
                for setting, pattern in config_checks.items():
                    if pattern in content:
                        found_settings.append(setting)
            except Exception:
                pass
        
        module_results["connection_settings"]["found"] = list(set(found_settings))
        
        # Check environment file
        env_file = Path(".env")
        if env_file.exists():
            env_content = env_file.read_text()
            module_results["connection_settings"]["env_has_token"] = "DISCORD_TOKEN=" in env_content
            
            # Check if token looks valid (without exposing it)
            if "DISCORD_TOKEN=" in env_content:
                for line in env_content.split('\n'):
                    if line.startswith("DISCORD_TOKEN="):
                        token_value = line.split('=', 1)[1].strip().strip('"\'')
                        if token_value and len(token_value) > 50:
                            module_results["connection_settings"]["token_looks_valid"] = True
                        else:
                            module_results["connection_settings"]["token_looks_valid"] = False
                        break
        
        self.results["modules"]["code_audit"] = module_results
    
    def generate_summary_recommendations(self):
        """Generate summary and actionable recommendations based on all findings."""
        print("\n📊 Generating Summary & Recommendations...")
        
        # Analyze critical issues
        critical_issues = []
        warnings = []
        
        # Check bot status
        bot_status = self.results["modules"].get("bot_status", {})
        if bot_status.get("errors"):
            if "Invalid token" in str(bot_status["errors"]):
                critical_issues.append("Invalid Discord bot token")
            elif "DISCORD_TOKEN environment variable not set" in str(bot_status["errors"]):
                critical_issues.append("Missing Discord bot token")
        
        # Check gateway limits
        gateway_info = bot_status.get("gateway_info", {})
        session_limits = gateway_info.get("session_start_limit", {})
        if session_limits.get("remaining", 1) == 0:
            critical_issues.append("No remaining gateway sessions")
        
        # Check multiple instances
        instances = self.results["modules"].get("instance_detection", {})
        if instances.get("processes", {}).get("count", 0) > 1:
            warnings.append(f"Multiple bot processes detected ({instances['processes']['count']})")
        if instances.get("containers", {}).get("count", 0) > 1:
            warnings.append(f"Multiple Docker containers running ({instances['containers']['count']})")
        
        # Check rate limiting
        rate_limit = self.results["modules"].get("rate_limiting", {})
        if rate_limit.get("rate_limit_status", {}).get("rate_limited"):
            critical_issues.append("Bot is currently rate limited")
        if rate_limit.get("ip_info", {}).get("is_vps_ip"):
            warnings.append("Running from VPS IP (may face stricter limits)")
        if rate_limit.get("cloudflare_check", {}).get("challenge_detected"):
            warnings.append("Cloudflare challenge detected")
        
        # Check code configuration
        code_audit = self.results["modules"].get("code_audit", {})
        intent_analysis = code_audit.get("intent_analysis", {})
        if intent_analysis.get("privileged_intents"):
            warnings.append(f"Using privileged intents: {', '.join(intent_analysis['privileged_intents'])}")
        if not intent_analysis.get("has_voice_states"):
            warnings.append("voice_states intent might be missing")
        
        # Generate recommendations
        recommendations = []
        
        if critical_issues:
            recommendations.append({
                "priority": "CRITICAL",
                "category": "Authentication",
                "issues": critical_issues,
                "actions": [
                    "Verify DISCORD_TOKEN is set correctly in .env file",
                    "Ensure token starts with correct prefix and has no extra spaces",
                    "Regenerate token in Discord Developer Portal if needed",
                    "Check bot hasn't been deleted or disabled"
                ]
            })
        
        if session_limits.get("remaining", 1) == 0:
            recommendations.append({
                "priority": "HIGH",
                "category": "Session Limits",
                "issues": ["Gateway session limit exhausted"],
                "actions": [
                    "Wait 24 hours for session limit reset",
                    "Or upgrade bot to get higher limits",
                    "Ensure proper session cleanup on bot shutdown",
                    "Implement session reuse instead of creating new ones"
                ]
            })
        
        if instances.get("processes", {}).get("count", 0) > 1 or instances.get("containers", {}).get("count", 0) > 1:
            recommendations.append({
                "priority": "HIGH",
                "category": "Multiple Instances",
                "issues": ["Multiple bot instances detected"],
                "actions": [
                    "Stop all bot instances: pkill -f robustty",
                    "Stop Docker containers: docker-compose down",
                    "Ensure only one instance runs at a time",
                    "Implement process locking mechanism"
                ]
            })
        
        if intent_analysis.get("privileged_intents"):
            recommendations.append({
                "priority": "MEDIUM",
                "category": "Bot Configuration",
                "issues": ["Privileged intents in use"],
                "actions": [
                    "Enable required intents in Discord Developer Portal",
                    "Go to Applications → Your Bot → Bot → Privileged Gateway Intents",
                    "Enable: SERVER MEMBERS INTENT, PRESENCE INTENT, MESSAGE CONTENT INTENT as needed",
                    "Save changes and wait a few minutes"
                ]
            })
        
        if rate_limit.get("ip_info", {}).get("is_vps_ip"):
            recommendations.append({
                "priority": "MEDIUM",
                "category": "VPS Deployment",
                "issues": ["VPS IP may face stricter rate limits"],
                "actions": [
                    "Implement exponential backoff for connections",
                    "Add longer delays between reconnection attempts",
                    "Consider using residential proxy for initial connection",
                    "Monitor rate limit headers closely"
                ]
            })
        
        # Update results
        self.results["summary"] = {
            "critical_issues": critical_issues,
            "warnings": warnings,
            "total_errors": sum(len(m.get("errors", [])) for m in self.results["modules"].values()),
            "authentication_status": "FAILED" if critical_issues else "OK",
            "environment_type": "VPS" if rate_limit.get("ip_info", {}).get("is_vps_ip") else "Local"
        }
        
        self.results["recommendations"] = recommendations
    
    def print_results(self):
        """Print formatted results."""
        print("\n" + "=" * 60)
        print("📋 DIAGNOSTIC SUMMARY")
        print("=" * 60)
        
        summary = self.results["summary"]
        print(f"\n🔸 Authentication Status: {summary['authentication_status']}")
        print(f"🔸 Environment Type: {summary['environment_type']}")
        print(f"🔸 Total Errors Found: {summary['total_errors']}")
        
        if summary["critical_issues"]:
            print(f"\n❌ Critical Issues ({len(summary['critical_issues'])})")
            for issue in summary["critical_issues"]:
                print(f"   • {issue}")
        
        if summary["warnings"]:
            print(f"\n⚠️  Warnings ({len(summary['warnings'])})")
            for warning in summary["warnings"]:
                print(f"   • {warning}")
        
        print("\n" + "=" * 60)
        print("💡 RECOMMENDATIONS")
        print("=" * 60)
        
        for rec in self.results["recommendations"]:
            print(f"\n[{rec['priority']}] {rec['category']}")
            print("Issues:")
            for issue in rec["issues"]:
                print(f"  • {issue}")
            print("Actions:")
            for i, action in enumerate(rec["actions"], 1):
                print(f"  {i}. {action}")
        
        # Save detailed results
        output_file = f"discord-530-diagnostic-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: {output_file}")


async def main():
    """Run comprehensive diagnostics."""
    diagnostics = DiscordAuthDiagnostics()
    
    try:
        await diagnostics.run_all_diagnostics()
        diagnostics.print_results()
        
        # Return exit code based on results
        if diagnostics.results["summary"]["critical_issues"]:
            return 1
        else:
            return 0
            
    except Exception as e:
        print(f"\n❌ Diagnostic failed with error: {e}")
        logger.exception("Diagnostic error")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)