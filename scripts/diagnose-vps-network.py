#!/usr/bin/env python3
"""
VPS Network Diagnostic Tool for Robustty Bot

This tool performs comprehensive network diagnostics to identify
connectivity issues in VPS deployments, specifically for Docker
containers running Discord bots.

Usage:
    python diagnose-vps-network.py [--json] [--verbose]
"""

import subprocess
import socket
import json
import sys
import time
import os
import argparse
from typing import Dict, List, Tuple, Optional
import urllib.request
import urllib.error
import ssl

class NetworkDiagnostics:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "issues": [],
            "warnings": [],
            "info": [],
            "tests": {}
        }
        
    def log(self, msg: str, level: str = "info"):
        """Log message with appropriate formatting"""
        if self.verbose or level in ["error", "warning"]:
            prefix = {
                "error": "❌ ERROR:",
                "warning": "⚠️  WARNING:",
                "success": "✅ SUCCESS:",
                "info": "ℹ️  INFO:"
            }.get(level, "")
            print(f"{prefix} {msg}")
            
        # Store in results
        if level == "error":
            self.results["issues"].append(msg)
        elif level == "warning":
            self.results["warnings"].append(msg)
        else:
            self.results["info"].append(msg)
    
    def run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[int, str, str]:
        """Run shell command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -2, "", str(e)
    
    def test_docker_installed(self) -> bool:
        """Test if Docker is installed and running"""
        self.log("Testing Docker installation...", "info")
        
        # Check if docker command exists
        code, stdout, stderr = self.run_command(["which", "docker"])
        if code != 0:
            self.log("Docker is not installed", "error")
            self.results["tests"]["docker_installed"] = False
            return False
            
        # Check if Docker daemon is running
        code, stdout, stderr = self.run_command(["docker", "info"], timeout=5)
        if code != 0:
            self.log("Docker daemon is not running", "error")
            self.log(f"Error: {stderr}", "error")
            self.results["tests"]["docker_running"] = False
            return False
            
        self.log("Docker is installed and running", "success")
        self.results["tests"]["docker_installed"] = True
        self.results["tests"]["docker_running"] = True
        return True
    
    def test_docker_network(self) -> bool:
        """Test Docker network configuration"""
        self.log("Testing Docker network configuration...", "info")
        
        # List Docker networks
        code, stdout, stderr = self.run_command(["docker", "network", "ls"])
        if code != 0:
            self.log("Failed to list Docker networks", "error")
            return False
            
        # Check if robustty-network exists
        if "robustty-network" in stdout or "robustty_robustty-network" in stdout:
            self.log("Robustty network exists", "success")
            network_name = "robustty-network" if "robustty-network" in stdout else "robustty_robustty-network"
            
            # Inspect network
            code, stdout, stderr = self.run_command(["docker", "network", "inspect", network_name])
            if code == 0:
                try:
                    network_info = json.loads(stdout)[0]
                    subnet = network_info.get("IPAM", {}).get("Config", [{}])[0].get("Subnet", "unknown")
                    self.log(f"Network subnet: {subnet}", "info")
                    self.results["tests"]["docker_network"] = {
                        "exists": True,
                        "subnet": subnet,
                        "driver": network_info.get("Driver", "unknown")
                    }
                except:
                    pass
        else:
            self.log("Robustty network not found", "warning")
            self.results["tests"]["docker_network"] = {"exists": False}
            
        return True
    
    def test_iptables(self) -> bool:
        """Test iptables configuration"""
        self.log("Testing iptables configuration...", "info")
        
        # Check if iptables is available
        code, stdout, stderr = self.run_command(["which", "iptables"])
        if code != 0:
            self.log("iptables not found (may be normal on some VPS)", "warning")
            return True
            
        # Check Docker iptables rules
        code, stdout, stderr = self.run_command(["sudo", "iptables", "-L", "DOCKER-USER", "-n"], timeout=5)
        if code == 0:
            self.log("DOCKER-USER chain exists", "success")
            if "RETURN" not in stdout:
                self.log("DOCKER-USER chain may be blocking traffic", "warning")
        else:
            self.log("DOCKER-USER chain not found", "info")
            
        # Check NAT rules
        code, stdout, stderr = self.run_command(["sudo", "iptables", "-t", "nat", "-L", "POSTROUTING", "-n"], timeout=5)
        if code == 0:
            if "MASQUERADE" in stdout:
                self.log("NAT masquerading is configured", "success")
            else:
                self.log("NAT masquerading may not be configured", "warning")
                
        # Check for common firewall issues
        code, stdout, stderr = self.run_command(["sudo", "iptables", "-L", "INPUT", "-n"], timeout=5)
        if code == 0 and "DROP" in stdout and "REJECT" in stdout:
            self.log("Restrictive INPUT rules detected", "warning")
            
        return True
    
    def test_container_connectivity(self) -> bool:
        """Test connectivity from inside Docker containers"""
        self.log("Testing container outbound connectivity...", "info")
        
        # Get running containers
        code, stdout, stderr = self.run_command(["docker", "ps", "--format", "{{.Names}}"])
        if code != 0:
            self.log("Failed to list running containers", "error")
            return False
            
        containers = stdout.strip().split('\n')
        robustty_container = None
        
        for container in containers:
            if "robustty" in container and "redis" not in container:
                robustty_container = container
                break
                
        if not robustty_container:
            self.log("Robustty container not running", "warning")
            self.results["tests"]["container_connectivity"] = {"running": False}
            return False
            
        # Test DNS resolution from container
        test_domains = ["google.com", "discord.com", "api.discord.com"]
        dns_results = {}
        
        for domain in test_domains:
            cmd = ["docker", "exec", robustty_container, "nslookup", domain]
            code, stdout, stderr = self.run_command(cmd, timeout=5)
            if code == 0:
                dns_results[domain] = "resolved"
                self.log(f"DNS resolution for {domain}: SUCCESS", "success")
            else:
                dns_results[domain] = "failed"
                self.log(f"DNS resolution for {domain}: FAILED", "error")
                
        # Test outbound HTTP connectivity
        cmd = ["docker", "exec", robustty_container, "python3", "-c",
               "import urllib.request; print(urllib.request.urlopen('http://example.com', timeout=5).status)"]
        code, stdout, stderr = self.run_command(cmd, timeout=10)
        
        if code == 0 and "200" in stdout:
            self.log("Outbound HTTP connectivity: SUCCESS", "success")
            http_test = True
        else:
            self.log("Outbound HTTP connectivity: FAILED", "error")
            http_test = False
            
        # Test Discord API connectivity
        cmd = ["docker", "exec", robustty_container, "python3", "-c",
               "import urllib.request; req = urllib.request.Request('https://discord.com/api/v10/gateway'); "
               "req.add_header('User-Agent', 'Robustty/1.0'); print(urllib.request.urlopen(req, timeout=5).status)"]
        code, stdout, stderr = self.run_command(cmd, timeout=10)
        
        if code == 0 and "200" in stdout:
            self.log("Discord API connectivity: SUCCESS", "success")
            discord_test = True
        else:
            self.log("Discord API connectivity: FAILED", "error")
            self.log(f"Error: {stderr}", "error")
            discord_test = False
            
        self.results["tests"]["container_connectivity"] = {
            "running": True,
            "dns": dns_results,
            "http": http_test,
            "discord_api": discord_test
        }
        
        return True
    
    def test_mtu_configuration(self) -> bool:
        """Test MTU configuration for Docker interfaces"""
        self.log("Testing MTU configuration...", "info")
        
        # Get Docker bridge interface
        code, stdout, stderr = self.run_command(["ip", "link", "show"])
        if code != 0:
            self.log("Failed to list network interfaces", "error")
            return False
            
        docker_interfaces = []
        lines = stdout.split('\n')
        for line in lines:
            if "docker" in line or "br-" in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    iface = parts[1].strip()
                    docker_interfaces.append(iface)
                    
        mtu_issues = []
        for iface in docker_interfaces:
            code, stdout, stderr = self.run_command(["ip", "link", "show", iface])
            if code == 0 and "mtu" in stdout:
                try:
                    mtu = int(stdout.split("mtu")[1].split()[0])
                    self.log(f"Interface {iface} MTU: {mtu}", "info")
                    if mtu < 1500:
                        mtu_issues.append(f"{iface}: MTU {mtu} is below standard")
                except:
                    pass
                    
        if mtu_issues:
            for issue in mtu_issues:
                self.log(issue, "warning")
            self.results["tests"]["mtu_configuration"] = {"issues": mtu_issues}
        else:
            self.log("MTU configuration looks good", "success")
            self.results["tests"]["mtu_configuration"] = {"issues": []}
            
        return True
    
    def test_discord_voice_servers(self) -> bool:
        """Test connectivity to Discord voice servers"""
        self.log("Testing Discord voice server connectivity...", "info")
        
        # Common Discord voice server regions
        voice_regions = [
            ("us-west", "us-west.discord.gg"),
            ("us-east", "us-east.discord.gg"),
            ("eu-central", "eu-central.discord.gg"),
            ("singapore", "singapore.discord.gg")
        ]
        
        results = {}
        for region, endpoint in voice_regions:
            try:
                # Try to resolve the endpoint
                ip = socket.gethostbyname(endpoint)
                results[region] = {"resolved": True, "ip": ip}
                self.log(f"Discord {region} resolved to {ip}", "success")
            except:
                results[region] = {"resolved": False}
                self.log(f"Failed to resolve Discord {region}", "warning")
                
        self.results["tests"]["discord_voice_servers"] = results
        return True
    
    def test_peertube_connectivity(self) -> bool:
        """Test connectivity to PeerTube instances"""
        self.log("Testing PeerTube connectivity...", "info")
        
        # Test common PeerTube instances
        instances = [
            "https://peertube.tv",
            "https://framatube.org",
            "https://video.blender.org"
        ]
        
        results = {}
        for instance in instances:
            try:
                # Create SSL context that accepts self-signed certificates
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                req = urllib.request.Request(f"{instance}/api/v1/config")
                req.add_header('User-Agent', 'Robustty/1.0')
                
                response = urllib.request.urlopen(req, timeout=10, context=ctx)
                results[instance] = {
                    "status": response.status,
                    "reachable": True
                }
                self.log(f"PeerTube instance {instance}: REACHABLE", "success")
            except urllib.error.HTTPError as e:
                results[instance] = {
                    "status": e.code,
                    "reachable": True,
                    "error": str(e)
                }
                self.log(f"PeerTube instance {instance}: HTTP {e.code}", "warning")
            except Exception as e:
                results[instance] = {
                    "reachable": False,
                    "error": str(e)
                }
                self.log(f"PeerTube instance {instance}: UNREACHABLE - {str(e)}", "error")
                
        self.results["tests"]["peertube_connectivity"] = results
        return True
    
    def test_odysee_api(self) -> bool:
        """Test Odysee API connectivity with timeout analysis"""
        self.log("Testing Odysee API connectivity...", "info")
        
        endpoints = [
            ("Search API", "https://lighthouse.odysee.tv/search", {"s": "test", "size": 1}),
            ("Resolve API", "https://api.na-backend.odysee.com/api/v1/proxy", {"method": "resolve", "params": {"urls": ["lbry://test"]}})
        ]
        
        results = {}
        for name, url, params in endpoints:
            start_time = time.time()
            try:
                if "proxy" in url:
                    # POST request for resolve API
                    data = json.dumps(params).encode('utf-8')
                    req = urllib.request.Request(url, data=data)
                    req.add_header('Content-Type', 'application/json')
                else:
                    # GET request for search API
                    query_string = urllib.parse.urlencode(params)
                    req = urllib.request.Request(f"{url}?{query_string}")
                    
                req.add_header('User-Agent', 'Robustty/1.0')
                
                response = urllib.request.urlopen(req, timeout=30)
                elapsed = time.time() - start_time
                
                results[name] = {
                    "status": response.status,
                    "reachable": True,
                    "response_time": f"{elapsed:.2f}s"
                }
                self.log(f"Odysee {name}: SUCCESS (took {elapsed:.2f}s)", "success")
                
            except urllib.error.URLError as e:
                elapsed = time.time() - start_time
                if "timed out" in str(e):
                    results[name] = {
                        "reachable": False,
                        "error": "Timeout",
                        "response_time": f"{elapsed:.2f}s"
                    }
                    self.log(f"Odysee {name}: TIMEOUT after {elapsed:.2f}s", "error")
                else:
                    results[name] = {
                        "reachable": False,
                        "error": str(e),
                        "response_time": f"{elapsed:.2f}s"
                    }
                    self.log(f"Odysee {name}: FAILED - {str(e)}", "error")
            except Exception as e:
                elapsed = time.time() - start_time
                results[name] = {
                    "reachable": False,
                    "error": str(e),
                    "response_time": f"{elapsed:.2f}s"
                }
                self.log(f"Odysee {name}: ERROR - {str(e)}", "error")
                
        self.results["tests"]["odysee_api"] = results
        return True
    
    def test_system_resources(self) -> bool:
        """Test system resources that might affect networking"""
        self.log("Testing system resources...", "info")
        
        # Check file descriptor limits
        code, stdout, stderr = self.run_command(["ulimit", "-n"])
        if code == 0:
            try:
                fd_limit = int(stdout.strip())
                if fd_limit < 4096:
                    self.log(f"Low file descriptor limit: {fd_limit}", "warning")
                else:
                    self.log(f"File descriptor limit: {fd_limit}", "info")
                self.results["tests"]["system_resources"] = {"fd_limit": fd_limit}
            except:
                pass
                
        # Check available memory
        code, stdout, stderr = self.run_command(["free", "-m"])
        if code == 0:
            lines = stdout.strip().split('\n')
            for line in lines:
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 7:
                        total = int(parts[1])
                        available = int(parts[6])
                        percent_free = (available / total) * 100
                        if percent_free < 10:
                            self.log(f"Low memory: {available}MB available of {total}MB ({percent_free:.1f}% free)", "warning")
                        else:
                            self.log(f"Memory: {available}MB available of {total}MB ({percent_free:.1f}% free)", "info")
                            
        return True
    
    def generate_report(self) -> Dict:
        """Generate comprehensive diagnostic report"""
        # Count issues by severity
        critical_issues = len(self.results["issues"])
        warnings = len(self.results["warnings"])
        
        # Generate recommendations
        recommendations = []
        
        if not self.results["tests"].get("docker_installed"):
            recommendations.append("Install Docker: curl -fsSL https://get.docker.com | sh")
            
        if not self.results["tests"].get("docker_running"):
            recommendations.append("Start Docker: sudo systemctl start docker")
            
        container_conn = self.results["tests"].get("container_connectivity", {})
        if container_conn.get("running") and not container_conn.get("discord_api"):
            recommendations.append("Check firewall rules for outbound HTTPS (port 443)")
            recommendations.append("Try running: sudo ./scripts/fix-vps-network.sh")
            
        if self.results["tests"].get("mtu_configuration", {}).get("issues"):
            recommendations.append("Fix MTU issues with: sudo ip link set dev docker0 mtu 1500")
            
        odysee_tests = self.results["tests"].get("odysee_api", {})
        for endpoint, result in odysee_tests.items():
            if not result.get("reachable") and "Timeout" in result.get("error", ""):
                recommendations.append(f"Odysee {endpoint} timing out - check VPS network latency")
                
        self.results["summary"] = {
            "critical_issues": critical_issues,
            "warnings": warnings,
            "recommendations": recommendations
        }
        
        return self.results
    
    def run_all_tests(self):
        """Run all diagnostic tests"""
        tests = [
            self.test_docker_installed,
            self.test_docker_network,
            self.test_iptables,
            self.test_container_connectivity,
            self.test_mtu_configuration,
            self.test_discord_voice_servers,
            self.test_peertube_connectivity,
            self.test_odysee_api,
            self.test_system_resources
        ]
        
        for test in tests:
            try:
                test()
            except Exception as e:
                self.log(f"Test {test.__name__} failed with error: {str(e)}", "error")
                
        return self.generate_report()

def main():
    parser = argparse.ArgumentParser(description="VPS Network Diagnostic Tool")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    print("🔍 Robustty VPS Network Diagnostics")
    print("=" * 50)
    
    diag = NetworkDiagnostics(verbose=args.verbose)
    report = diag.run_all_tests()
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n📊 DIAGNOSTIC SUMMARY")
        print("=" * 50)
        print(f"Critical Issues: {report['summary']['critical_issues']}")
        print(f"Warnings: {report['summary']['warnings']}")
        
        if report['summary']['recommendations']:
            print("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(report['summary']['recommendations'], 1):
                print(f"{i}. {rec}")
        
        if report['summary']['critical_issues'] == 0:
            print("\n✅ No critical issues found!")
        else:
            print("\n❌ Critical issues detected. Please review the recommendations above.")
            
        print("\nFor detailed results, run with --json flag")

if __name__ == "__main__":
    main()