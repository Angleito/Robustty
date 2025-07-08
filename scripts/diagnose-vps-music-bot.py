#!/usr/bin/env python3
"""
Comprehensive VPS Discord Music Bot Diagnostic Tool
Tests all possible issues that could prevent bot from playing music
Optimized for VPS environments with limited resources
"""

import asyncio
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import concurrent.futures
import shutil

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")

def print_section(text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}▶ {text}{Colors.ENDC}")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")

class VPSMusicBotDiagnostics:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.fixes = []
        self.env_vars = {}
        self.load_env()
        
    def load_env(self):
        """Load environment variables from .env file"""
        env_path = Path('.env')
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        self.env_vars[key] = value.strip('"\'')
        
    def run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    async def test_discord_connection(self):
        """Test Discord connection issues"""
        print_section("Testing Discord Connection")
        
        # Check token
        token = self.env_vars.get('DISCORD_TOKEN', '')
        if not token or token in ['your_discord_bot_token_here', 'YOUR_ACTUAL_BOT_TOKEN_HERE']:
            print_error("Invalid Discord token in .env file")
            self.issues.append("Discord token not configured")
            self.fixes.append("Update DISCORD_TOKEN in .env with valid bot token")
            return
        
        print_success(f"Discord token found (length: {len(token)})")
        
        # Test Discord API
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bot {token}"}
                async with session.get(
                    "https://discord.com/api/v10/users/@me",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print_success(f"Discord API authenticated as: {data.get('username')}#{data.get('discriminator')}")
                    elif resp.status == 401:
                        print_error("Discord token is invalid or expired")
                        self.issues.append("Invalid Discord token")
                        self.fixes.append("Regenerate token at https://discord.com/developers/applications")
                    else:
                        print_error(f"Discord API error: {resp.status}")
                        self.issues.append(f"Discord API returned {resp.status}")
        except Exception as e:
            print_error(f"Failed to connect to Discord API: {e}")
            self.issues.append("Cannot reach Discord API")
            
        # Test gateway connectivity
        print_info("Testing Discord Gateway...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.com/api/v10/gateway",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print_success(f"Gateway URL: {data.get('url')}")
                    else:
                        print_error(f"Gateway endpoint returned: {resp.status}")
        except Exception as e:
            print_error(f"Gateway test failed: {e}")
            self.issues.append("Cannot reach Discord gateway")
    
    def test_vps_network(self):
        """Test VPS network issues"""
        print_section("Testing VPS Network Configuration")
        
        # Test DNS resolution
        print_info("Testing DNS resolution...")
        dns_tests = [
            ("discord.com", "Discord"),
            ("gateway.discord.gg", "Discord Gateway"),
            ("youtube.com", "YouTube"),
            ("api.rumble.com", "Rumble"),
            ("odysee.com", "Odysee")
        ]
        
        dns_failures = []
        for host, service in dns_tests:
            try:
                socket.gethostbyname(host)
                print_success(f"DNS resolution for {service}: OK")
            except socket.gaierror:
                print_error(f"DNS resolution failed for {service}")
                dns_failures.append(service)
        
        if dns_failures:
            self.issues.append(f"DNS resolution failed for: {', '.join(dns_failures)}")
            self.fixes.append("Add reliable DNS servers: echo 'nameserver 8.8.8.8' | sudo tee -a /etc/resolv.conf")
        
        # Test outbound ports
        print_info("Testing outbound ports...")
        port_tests = [
            (443, "discord.com", "HTTPS/WSS"),
            (80, "youtube.com", "HTTP"),
            (443, "youtube.com", "HTTPS")
        ]
        
        for port, host, desc in port_tests:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                result = sock.connect_ex((host, port))
                if result == 0:
                    print_success(f"Port {port} ({desc}) to {host}: OPEN")
                else:
                    print_error(f"Port {port} ({desc}) to {host}: BLOCKED")
                    self.issues.append(f"Outbound port {port} blocked")
            except Exception as e:
                print_error(f"Port test failed: {e}")
            finally:
                sock.close()
        
        # Check firewall
        print_info("Checking firewall rules...")
        returncode, stdout, stderr = self.run_command(["sudo", "iptables", "-L", "-n"])
        if returncode == 0:
            if "DROP" in stdout or "REJECT" in stdout:
                print_warning("Firewall has DROP/REJECT rules - verify Discord/streaming ports are allowed")
                self.warnings.append("Firewall may be blocking connections")
        
        # Test MTU
        print_info("Testing network MTU...")
        returncode, stdout, stderr = self.run_command(["ip", "link", "show"])
        if returncode == 0 and "mtu" in stdout:
            # Extract MTU values
            lines = stdout.split('\n')
            for line in lines:
                if "mtu" in line and "docker" not in line:
                    try:
                        mtu = int(line.split("mtu")[1].split()[0])
                        if mtu < 1500:
                            print_warning(f"Low MTU detected: {mtu} (standard is 1500)")
                            self.warnings.append(f"Low network MTU: {mtu}")
                    except:
                        pass
    
    def test_voice_connection(self):
        """Test Discord voice connection requirements"""
        print_section("Testing Voice Connection Requirements")
        
        # Check UDP port range
        print_info("Checking UDP port range 50000-50010...")
        returncode, stdout, stderr = self.run_command(["sudo", "netstat", "-uln"])
        if returncode != 0:
            # Try ss as fallback
            returncode, stdout, stderr = self.run_command(["ss", "-uln"])
        
        if returncode == 0:
            print_success("UDP port check completed")
        else:
            print_warning("Could not verify UDP ports (non-critical)")
        
        # Check Docker port mapping
        print_info("Checking Docker port mappings...")
        returncode, stdout, stderr = self.run_command(["docker", "ps", "--format", "table {{.Ports}}"])
        if returncode == 0:
            if "50000-50010" in stdout:
                print_success("Voice UDP ports are mapped in Docker")
            else:
                print_error("Voice UDP ports not mapped in Docker")
                self.issues.append("UDP ports 50000-50010 not mapped")
                self.fixes.append("Add to docker-compose.yml: ports: - '50000-50010:50000-50010/udp'")
    
    def test_audio_streaming(self):
        """Test audio streaming dependencies"""
        print_section("Testing Audio Streaming Components")
        
        # Check FFmpeg
        print_info("Checking FFmpeg installation...")
        ffmpeg_locations = [
            shutil.which("ffmpeg"),
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg"
        ]
        
        ffmpeg_found = False
        for loc in ffmpeg_locations:
            if loc and os.path.exists(loc):
                returncode, stdout, stderr = self.run_command([loc, "-version"])
                if returncode == 0:
                    version = stdout.split('\n')[0]
                    print_success(f"FFmpeg found: {version}")
                    ffmpeg_found = True
                    break
        
        if not ffmpeg_found:
            print_error("FFmpeg not found")
            self.issues.append("FFmpeg not installed")
            self.fixes.append("Install FFmpeg: sudo apt-get install -y ffmpeg")
        
        # Check yt-dlp/youtube-dl
        print_info("Checking yt-dlp/youtube-dl...")
        ytdl_found = False
        for cmd in ["yt-dlp", "youtube-dl"]:
            if shutil.which(cmd):
                returncode, stdout, stderr = self.run_command([cmd, "--version"])
                if returncode == 0:
                    print_success(f"{cmd} found: {stdout.strip()}")
                    ytdl_found = True
                    break
        
        if not ytdl_found:
            # Check if it's in Python packages
            try:
                import yt_dlp
                print_success("yt-dlp Python module found")
                ytdl_found = True
            except ImportError:
                try:
                    import youtube_dl
                    print_success("youtube-dl Python module found")
                    ytdl_found = True
                except ImportError:
                    pass
        
        if not ytdl_found:
            print_warning("yt-dlp/youtube-dl not found (handled by bot internally)")
        
        # Check API keys
        print_info("Checking streaming service API keys...")
        if self.env_vars.get('YOUTUBE_API_KEY') and self.env_vars.get('YOUTUBE_API_KEY') != 'your_youtube_api_key_here':
            print_success("YouTube API key configured")
        else:
            print_warning("YouTube API key not configured (search may be limited)")
            self.warnings.append("YouTube API key missing")
        
        if self.env_vars.get('APIFY_API_KEY') and self.env_vars.get('APIFY_API_KEY') != 'your_apify_api_key_here':
            print_success("Apify API key configured (for Rumble)")
        else:
            print_warning("Apify API key not configured (Rumble search disabled)")
        
        # Check cookies
        print_info("Checking cookie files...")
        cookie_dir = Path("cookies")
        if cookie_dir.exists():
            cookie_files = list(cookie_dir.glob("*.txt")) + list(cookie_dir.glob("*.json"))
            if cookie_files:
                print_success(f"Found {len(cookie_files)} cookie files")
                for cf in cookie_files:
                    print_info(f"  - {cf.name}")
            else:
                print_warning("No cookie files found (may limit access to some content)")
        else:
            print_warning("Cookie directory not found")
    
    def test_vps_system(self):
        """Test VPS system health"""
        print_section("Testing VPS System Health")
        
        # Check time sync
        print_info("Checking system time synchronization...")
        returncode, stdout, stderr = self.run_command(["timedatectl", "status"])
        if returncode == 0:
            if "synchronized: yes" in stdout:
                print_success("System time is synchronized")
            else:
                print_error("System time not synchronized")
                self.issues.append("Time not synchronized")
                self.fixes.append("Fix time sync: sudo timedatectl set-ntp true")
        
        # Check system resources
        print_info("Checking system resources...")
        
        # Memory
        returncode, stdout, stderr = self.run_command(["free", "-m"])
        if returncode == 0:
            lines = stdout.split('\n')
            for line in lines:
                if line.startswith('Mem:'):
                    parts = line.split()
                    total_mem = int(parts[1])
                    used_mem = int(parts[2])
                    free_mem = int(parts[3])
                    mem_percent = (used_mem / total_mem) * 100
                    
                    if total_mem < 1024:
                        print_warning(f"Low total memory: {total_mem}MB (recommend 1GB+)")
                        self.warnings.append("Low system memory")
                    
                    if mem_percent > 90:
                        print_error(f"High memory usage: {mem_percent:.1f}%")
                        self.issues.append("High memory usage")
                    else:
                        print_success(f"Memory usage: {mem_percent:.1f}% ({free_mem}MB free)")
        
        # Disk space
        returncode, stdout, stderr = self.run_command(["df", "-h", "/"])
        if returncode == 0:
            lines = stdout.split('\n')
            for line in lines[1:]:
                if line:
                    parts = line.split()
                    if len(parts) >= 5:
                        usage = parts[4].rstrip('%')
                        if int(usage) > 90:
                            print_error(f"Low disk space: {usage}% used")
                            self.issues.append("Low disk space")
                        else:
                            print_success(f"Disk usage: {usage}%")
        
        # Docker status
        print_info("Checking Docker status...")
        returncode, stdout, stderr = self.run_command(["docker", "info"])
        if returncode == 0:
            print_success("Docker is running")
            
            # Check containers
            returncode, stdout, stderr = self.run_command(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"])
            if returncode == 0:
                print_info("Docker containers:")
                for line in stdout.split('\n')[1:]:
                    if line:
                        print_info(f"  {line}")
        else:
            print_error("Docker not running or not accessible")
            self.issues.append("Docker not running")
            self.fixes.append("Start Docker: sudo systemctl start docker")
        
        # Redis connectivity
        print_info("Checking Redis connectivity...")
        returncode, stdout, stderr = self.run_command(["docker", "exec", "robustty-redis", "redis-cli", "ping"])
        if returncode == 0 and "PONG" in stdout:
            print_success("Redis is responding")
        else:
            # Try direct connection
            returncode, stdout, stderr = self.run_command(["redis-cli", "ping"])
            if returncode == 0 and "PONG" in stdout:
                print_success("Redis is responding (host)")
            else:
                print_error("Redis not responding")
                self.issues.append("Redis not accessible")
    
    def test_vps_specific(self):
        """Test VPS-specific issues"""
        print_section("Testing VPS-Specific Issues")
        
        # Detect VPS provider
        print_info("Detecting VPS provider...")
        provider = "Unknown"
        
        # Check various methods to detect provider
        checks = [
            ("/sys/devices/virtual/dmi/id/sys_vendor", "DMI vendor"),
            ("/sys/devices/virtual/dmi/id/product_name", "DMI product"),
            ("/sys/hypervisor/uuid", "Hypervisor UUID"),
        ]
        
        for path, desc in checks:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        content = f.read().strip().lower()
                        if 'digitalocean' in content:
                            provider = "DigitalOcean"
                        elif 'vultr' in content:
                            provider = "Vultr"
                        elif 'linode' in content:
                            provider = "Linode"
                        elif 'amazon' in content or 'ec2' in content:
                            provider = "AWS EC2"
                        elif 'google' in content or 'gce' in content:
                            provider = "Google Cloud"
                except:
                    pass
        
        # Check hostname/kernel
        returncode, stdout, stderr = self.run_command(["uname", "-a"])
        if returncode == 0:
            if 'vultr' in stdout.lower():
                provider = "Vultr"
        
        print_info(f"VPS Provider: {provider}")
        
        # Check IP reputation
        print_info("Checking IP reputation...")
        returncode, stdout, stderr = self.run_command(["curl", "-s", "https://ipinfo.io/json"])
        if returncode == 0:
            try:
                ip_data = json.loads(stdout)
                ip = ip_data.get('ip', 'Unknown')
                org = ip_data.get('org', 'Unknown')
                print_info(f"Public IP: {ip}")
                print_info(f"Organization: {org}")
                
                # Known problematic providers
                if any(bad in org.lower() for bad in ['ovh', 'hetzner', 'contabo']):
                    print_warning("This VPS provider may have IP reputation issues with Discord")
                    self.warnings.append("VPS provider may have IP reputation issues")
            except:
                pass
        
        # Check for IPv6
        print_info("Checking IPv6 connectivity...")
        returncode, stdout, stderr = self.run_command(["ip", "-6", "addr"])
        if returncode == 0 and "inet6" in stdout:
            # Try to connect via IPv6
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                result = sock.connect_ex(("2001:4860:4860::8888", 53))  # Google DNS IPv6
                if result == 0:
                    print_success("IPv6 connectivity working")
                else:
                    print_warning("IPv6 configured but not working")
                    self.warnings.append("IPv6 connectivity issues")
            except:
                print_warning("IPv6 test failed")
            finally:
                sock.close()
        else:
            print_info("IPv6 not configured (this is OK)")
    
    async def run_diagnostics(self, auto_fix: bool = False):
        """Run all diagnostic tests"""
        print_header("VPS Discord Music Bot Diagnostics")
        print_info(f"Running on: {platform.platform()}")
        print_info(f"Python version: {sys.version.split()[0]}")
        print_info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run tests
        await self.test_discord_connection()
        self.test_vps_network()
        self.test_voice_connection()
        self.test_audio_streaming()
        self.test_vps_system()
        self.test_vps_specific()
        
        # Summary
        print_header("Diagnostic Summary")
        
        if self.issues:
            print_error(f"Found {len(self.issues)} critical issues:")
            for issue in self.issues:
                print_error(f"  • {issue}")
        else:
            print_success("No critical issues found!")
        
        if self.warnings:
            print_warning(f"Found {len(self.warnings)} warnings:")
            for warning in self.warnings:
                print_warning(f"  • {warning}")
        
        if self.fixes:
            print_section("Recommended Fixes")
            for i, fix in enumerate(self.fixes, 1):
                print_info(f"{i}. {fix}")
        
        # Auto-fix option
        if auto_fix and self.fixes:
            print_section("Auto-Fix Available")
            print_warning("Would you like to apply automatic fixes? (safe fixes only)")
            response = input("Apply fixes? [y/N]: ").lower()
            if response == 'y':
                await self.apply_fixes()
        
        # Generate report
        self.generate_report()
    
    async def apply_fixes(self):
        """Apply automatic fixes for common issues"""
        print_section("Applying Automatic Fixes")
        
        # Add DNS servers
        if any("DNS resolution" in issue for issue in self.issues):
            print_info("Adding reliable DNS servers...")
            subprocess.run(["sudo", "bash", "-c", "echo 'nameserver 8.8.8.8' >> /etc/resolv.conf"])
            subprocess.run(["sudo", "bash", "-c", "echo 'nameserver 1.1.1.1' >> /etc/resolv.conf"])
            print_success("DNS servers added")
        
        # Fix time sync
        if any("Time not synchronized" in issue for issue in self.issues):
            print_info("Enabling time synchronization...")
            subprocess.run(["sudo", "timedatectl", "set-ntp", "true"])
            print_success("Time sync enabled")
        
        # Install FFmpeg
        if any("FFmpeg not installed" in issue for issue in self.issues):
            print_info("Installing FFmpeg...")
            subprocess.run(["sudo", "apt-get", "update"])
            subprocess.run(["sudo", "apt-get", "install", "-y", "ffmpeg"])
            print_success("FFmpeg installed")
    
    def generate_report(self):
        """Generate a diagnostic report file"""
        report_path = Path("vps-diagnostic-report.txt")
        with open(report_path, 'w') as f:
            f.write("VPS Discord Music Bot Diagnostic Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Platform: {platform.platform()}\n")
            f.write(f"Python: {sys.version.split()[0]}\n\n")
            
            f.write("ISSUES FOUND:\n")
            for issue in self.issues:
                f.write(f"- {issue}\n")
            
            f.write("\nWARNINGS:\n")
            for warning in self.warnings:
                f.write(f"- {warning}\n")
            
            f.write("\nRECOMMENDED FIXES:\n")
            for fix in self.fixes:
                f.write(f"- {fix}\n")
        
        print_info(f"Diagnostic report saved to: {report_path}")

async def main():
    """Main entry point"""
    # Check if running with required libraries
    try:
        import aiohttp
    except ImportError:
        print_error("Missing required library: aiohttp")
        print_info("Install with: pip install aiohttp")
        sys.exit(1)
    
    # Parse arguments
    auto_fix = "--fix" in sys.argv
    
    # Run diagnostics
    diagnostics = VPSMusicBotDiagnostics()
    await diagnostics.run_diagnostics(auto_fix)

if __name__ == "__main__":
    # Check if running as root (some tests need it)
    if os.geteuid() != 0 and "--no-sudo" not in sys.argv:
        print_warning("Some tests require sudo access. Run with sudo for complete diagnostics.")
        print_info("Or use --no-sudo to skip privileged tests")
    
    # Run async main
    asyncio.run(main())