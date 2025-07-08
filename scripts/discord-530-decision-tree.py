#!/usr/bin/env python3
"""
Discord 530 Decision Tree - Quick diagnostic and guided troubleshooting.
Interactive troubleshooting that guides users through step-by-step diagnosis.
"""

import os
import sys
import asyncio
import json
import time
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import aiohttp
import subprocess
import psutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DecisionNode:
    """Represents a node in the decision tree."""
    
    def __init__(
        self,
        name: str,
        question: str,
        check_function: Optional[callable] = None,
        yes_node: Optional['DecisionNode'] = None,
        no_node: Optional['DecisionNode'] = None,
        actions: Optional[List[str]] = None,
        is_terminal: bool = False
    ):
        self.name = name
        self.question = question
        self.check_function = check_function
        self.yes_node = yes_node
        self.no_node = no_node
        self.actions = actions or []
        self.is_terminal = is_terminal
        self.result = None


class Discord530DecisionTree:
    """Interactive decision tree for Discord 530 troubleshooting."""
    
    def __init__(self):
        self.token = os.getenv("DISCORD_TOKEN", "").strip()
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": [],
            "findings": {},
            "recommendations": []
        }
        self.tree = self._build_decision_tree()
    
    def _build_decision_tree(self) -> DecisionNode:
        """Build the complete decision tree structure."""
        
        # Terminal nodes with solutions
        invalid_token = DecisionNode(
            name="invalid_token",
            question="",
            is_terminal=True,
            actions=[
                "1. Check .env file for DISCORD_TOKEN=your_token",
                "2. Verify token has no extra spaces or quotes",
                "3. Regenerate token in Discord Developer Portal",
                "4. Ensure bot hasn't been deleted"
            ]
        )
        
        missing_token = DecisionNode(
            name="missing_token",
            question="",
            is_terminal=True,
            actions=[
                "1. Create .env file in project root",
                "2. Add line: DISCORD_TOKEN=your_bot_token",
                "3. Get token from Discord Developer Portal",
                "4. Restart the bot application"
            ]
        )
        
        session_limit_exceeded = DecisionNode(
            name="session_limit_exceeded",
            question="",
            is_terminal=True,
            actions=[
                "1. Wait 24 hours for session limit reset",
                "2. Or verify bot in Discord Developer Portal for higher limits",
                "3. Stop all running instances: pkill -f robustty",
                "4. Ensure proper bot shutdown to free sessions"
            ]
        )
        
        multiple_instances_found = DecisionNode(
            name="multiple_instances",
            question="",
            is_terminal=True,
            actions=[
                "1. Stop all instances: pkill -f robustty",
                "2. Stop Docker: docker-compose down",
                "3. Wait 30 seconds for cleanup",
                "4. Start only one instance"
            ]
        )
        
        privileged_intents_issue = DecisionNode(
            name="privileged_intents",
            question="",
            is_terminal=True,
            actions=[
                "1. Go to Discord Developer Portal",
                "2. Select your application → Bot",
                "3. Enable required Privileged Gateway Intents",
                "4. Save and wait 5 minutes before testing"
            ]
        )
        
        rate_limit_issue = DecisionNode(
            name="rate_limited",
            question="",
            is_terminal=True,
            actions=[
                "1. Wait for rate limit to reset (check Retry-After header)",
                "2. Implement exponential backoff in code",
                "3. Reduce connection frequency",
                "4. Consider VPS-specific optimizations if on VPS"
            ]
        )
        
        network_connectivity_issue = DecisionNode(
            name="network_issue",
            question="",
            is_terminal=True,
            actions=[
                "1. Check internet connection",
                "2. Test: ping discord.com",
                "3. Check firewall/proxy settings",
                "4. Try different network if possible"
            ]
        )
        
        code_configuration_issue = DecisionNode(
            name="config_issue",
            question="",
            is_terminal=True,
            actions=[
                "1. Check discord.py version (should be ≥ 2.0)",
                "2. Verify bot intents match Discord portal settings",
                "3. Check for multiple bot.run() calls",
                "4. Review connection settings in code"
            ]
        )
        
        unknown_issue = DecisionNode(
            name="unknown",
            question="",
            is_terminal=True,
            actions=[
                "1. Run comprehensive diagnostic: python scripts/diagnose-discord-530-comprehensive.py",
                "2. Check Discord status: https://discordstatus.com",
                "3. Review bot logs for additional error details",
                "4. Contact Discord support if issue persists"
            ]
        )
        
        # Decision nodes
        check_rate_limits = DecisionNode(
            name="check_rate_limits",
            question="Is the bot currently rate limited?",
            check_function=self._check_rate_limits,
            yes_node=rate_limit_issue,
            no_node=None  # Will be set later
        )
        
        check_network = DecisionNode(
            name="check_network",
            question="Can you reach Discord servers?",
            check_function=self._check_network_connectivity,
            yes_node=check_rate_limits,
            no_node=network_connectivity_issue
        )
        
        check_privileged_intents = DecisionNode(
            name="check_privileged_intents",
            question="Are privileged intents properly configured?",
            check_function=self._check_privileged_intents,
            yes_node=check_network,
            no_node=privileged_intents_issue
        )
        
        check_code_config = DecisionNode(
            name="check_code_config",
            question="Is the code configuration correct?",
            check_function=self._check_code_configuration,
            yes_node=check_privileged_intents,
            no_node=code_configuration_issue
        )
        
        check_multiple_instances = DecisionNode(
            name="check_multiple_instances",
            question="Are there multiple bot instances running?",
            check_function=self._check_multiple_instances,
            yes_node=multiple_instances_found,
            no_node=check_code_config
        )
        
        check_session_limits = DecisionNode(
            name="check_session_limits",
            question="Has the bot exceeded session limits?",
            check_function=self._check_session_limits,
            yes_node=session_limit_exceeded,
            no_node=check_multiple_instances
        )
        
        check_token_validity = DecisionNode(
            name="check_token_validity",
            question="Is the Discord token valid?",
            check_function=self._check_token_validity,
            yes_node=check_session_limits,
            no_node=None  # Will be set based on token presence
        )
        
        check_token_exists = DecisionNode(
            name="check_token_exists",
            question="Is the Discord token set?",
            check_function=self._check_token_exists,
            yes_node=check_token_validity,
            no_node=missing_token
        )
        
        # Set the no_node for check_token_validity based on token existence
        check_token_validity.no_node = invalid_token
        
        # Set the no_node for check_rate_limits
        check_rate_limits.no_node = unknown_issue
        
        return check_token_exists
    
    async def _check_token_exists(self) -> bool:
        """Check if Discord token is set in environment."""
        exists = bool(self.token)
        self.results["findings"]["token_exists"] = exists
        if not exists:
            print("  ✗ DISCORD_TOKEN environment variable not found")
        else:
            print(f"  ✓ Token found (length: {len(self.token)})")
        return exists
    
    async def _check_token_validity(self) -> bool:
        """Check if the Discord token is valid by making API call."""
        if not self.token:
            return False
            
        try:
            headers = {"Authorization": f"Bot {self.token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.com/api/v10/users/@me",
                    headers=headers,
                    timeout=10
                ) as resp:
                    valid = resp.status == 200
                    self.results["findings"]["token_valid"] = valid
                    
                    if valid:
                        bot_data = await resp.json()
                        print(f"  ✓ Token valid - Bot: {bot_data.get('username', 'Unknown')}")
                        self.results["findings"]["bot_info"] = {
                            "username": bot_data.get("username"),
                            "id": bot_data.get("id")
                        }
                    else:
                        print(f"  ✗ Token invalid - API returned {resp.status}")
                        
                    return valid
                    
        except Exception as e:
            print(f"  ✗ Token validation failed: {type(e).__name__}")
            self.results["findings"]["token_valid"] = False
            self.results["findings"]["token_error"] = str(e)
            return False
    
    async def _check_session_limits(self) -> bool:
        """Check if bot has exceeded Discord session limits."""
        if not self.token:
            return False
            
        try:
            headers = {"Authorization": f"Bot {self.token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.com/api/v10/gateway/bot",
                    headers=headers,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        limits = data.get("session_start_limit", {})
                        remaining = limits.get("remaining", 1)
                        total = limits.get("total", 1000)
                        
                        self.results["findings"]["session_limits"] = limits
                        exceeded = remaining == 0
                        
                        if exceeded:
                            print(f"  ✗ Session limit exceeded: {remaining}/{total} remaining")
                        else:
                            print(f"  ✓ Session limits OK: {remaining}/{total} remaining")
                            
                        return exceeded
                    else:
                        print(f"  ✗ Cannot check session limits - API returned {resp.status}")
                        return False
                        
        except Exception as e:
            print(f"  ✗ Session limit check failed: {type(e).__name__}")
            return False
    
    async def _check_multiple_instances(self) -> bool:
        """Check for multiple bot instances running."""
        try:
            current_pid = os.getpid()
            bot_processes = []
            
            # Check Python processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    info = proc.info
                    if info['name'] in ['python', 'python3']:
                        cmdline = ' '.join(info['cmdline'] or [])
                        if 'robustty' in cmdline.lower() or 'main.py' in cmdline:
                            bot_processes.append({
                                "pid": info['pid'],
                                "is_current": info['pid'] == current_pid,
                                "cmdline": cmdline[:80] + "..." if len(cmdline) > 80 else cmdline
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Check Docker containers
            docker_containers = 0
            try:
                result = subprocess.run(
                    ["docker", "ps", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    containers = result.stdout.strip().split('\n')
                    docker_containers = len([c for c in containers if 'robustty' in c.lower()])
            except Exception:
                pass
            
            multiple = len(bot_processes) > 1 or docker_containers > 1
            
            self.results["findings"]["multiple_instances"] = {
                "python_processes": len(bot_processes),
                "docker_containers": docker_containers,
                "processes": bot_processes
            }
            
            if multiple:
                print(f"  ⚠️ Multiple instances found: {len(bot_processes)} Python, {docker_containers} Docker")
            else:
                print(f"  ✓ Single instance: {len(bot_processes)} Python, {docker_containers} Docker")
                
            return multiple
            
        except Exception as e:
            print(f"  ✗ Instance check failed: {type(e).__name__}")
            return False
    
    async def _check_code_configuration(self) -> bool:
        """Check for common code configuration issues."""
        issues = []
        
        # Check discord.py version
        try:
            import discord
            version = discord.__version__
            major, minor = map(int, version.split('.')[:2])
            if major < 2:
                issues.append(f"Outdated discord.py version: {version} (need ≥ 2.0)")
        except ImportError:
            issues.append("discord.py not installed")
        
        # Check bot file exists
        bot_file = Path("src/bot/bot.py")
        if not bot_file.exists():
            issues.append("Bot file (src/bot/bot.py) not found")
        else:
            # Check for common issues in bot code
            try:
                content = bot_file.read_text()
                
                # Count bot.run() calls
                run_calls = content.count(".run(") + content.count(".start(")
                if run_calls > 1:
                    issues.append(f"Multiple bot.run() calls found ({run_calls})")
                
                # Check for basic intents
                if "discord.Intents" not in content:
                    issues.append("No intent configuration found")
                    
            except Exception:
                issues.append("Cannot read bot file")
        
        # Check .env file
        env_file = Path(".env")
        if env_file.exists():
            try:
                env_content = env_file.read_text()
                if "DISCORD_TOKEN=" not in env_content:
                    issues.append("DISCORD_TOKEN not found in .env file")
            except Exception:
                issues.append("Cannot read .env file")
        else:
            issues.append(".env file not found")
        
        self.results["findings"]["code_issues"] = issues
        
        if issues:
            print(f"  ✗ Configuration issues found:")
            for issue in issues[:3]:  # Show first 3 issues
                print(f"    • {issue}")
            if len(issues) > 3:
                print(f"    • ... and {len(issues) - 3} more")
        else:
            print("  ✓ Code configuration looks good")
            
        return len(issues) == 0
    
    async def _check_privileged_intents(self) -> bool:
        """Check if privileged intents are properly configured."""
        if not Path("src/bot/bot.py").exists():
            return True  # Skip if no bot file
            
        try:
            content = Path("src/bot/bot.py").read_text()
            
            # Look for privileged intents
            privileged_patterns = [
                "message_content", "members", "presences"
            ]
            
            found_privileged = []
            for pattern in privileged_patterns:
                if pattern in content:
                    found_privileged.append(pattern)
            
            self.results["findings"]["privileged_intents"] = found_privileged
            
            if found_privileged:
                print(f"  ⚠️ Privileged intents in use: {', '.join(found_privileged)}")
                print("    Make sure these are enabled in Discord Developer Portal!")
                return False  # Assume they might not be configured in portal
            else:
                print("  ✓ No privileged intents detected")
                return True
                
        except Exception:
            print("  ? Cannot check intent configuration")
            return True  # Assume OK if can't check
    
    async def _check_network_connectivity(self) -> bool:
        """Check basic network connectivity to Discord."""
        try:
            # Test Discord API connectivity
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.com/api/v10/gateway",
                    timeout=5
                ) as resp:
                    api_ok = resp.status < 400
                    
                # Test WebSocket gateway
                try:
                    import websockets
                    async with websockets.connect(
                        "wss://gateway.discord.gg",
                        timeout=5
                    ) as ws:
                        ws_ok = True
                except Exception:
                    ws_ok = False
                
                connectivity_ok = api_ok and ws_ok
                
                self.results["findings"]["network_connectivity"] = {
                    "api_reachable": api_ok,
                    "websocket_reachable": ws_ok
                }
                
                if connectivity_ok:
                    print("  ✓ Discord servers reachable")
                else:
                    print(f"  ✗ Connectivity issues - API: {api_ok}, WS: {ws_ok}")
                    
                return connectivity_ok
                
        except Exception as e:
            print(f"  ✗ Network check failed: {type(e).__name__}")
            self.results["findings"]["network_error"] = str(e)
            return False
    
    async def _check_rate_limits(self) -> bool:
        """Check if bot is currently rate limited."""
        if not self.token:
            return False
            
        try:
            headers = {"Authorization": f"Bot {self.token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.com/api/v10/users/@me",
                    headers=headers,
                    timeout=10
                ) as resp:
                    rate_limited = resp.status == 429
                    
                    # Check rate limit headers
                    rate_headers = {
                        "remaining": resp.headers.get("X-RateLimit-Remaining"),
                        "limit": resp.headers.get("X-RateLimit-Limit"),
                        "reset_after": resp.headers.get("X-RateLimit-Reset-After"),
                        "retry_after": resp.headers.get("Retry-After")
                    }
                    
                    self.results["findings"]["rate_limit_status"] = {
                        "is_rate_limited": rate_limited,
                        "headers": rate_headers
                    }
                    
                    if rate_limited:
                        retry_after = rate_headers.get("retry_after", "unknown")
                        print(f"  ✗ Rate limited! Retry after: {retry_after}s")
                    else:
                        remaining = rate_headers.get("remaining", "?")
                        limit = rate_headers.get("limit", "?")
                        print(f"  ✓ Not rate limited ({remaining}/{limit} remaining)")
                        
                    return rate_limited
                    
        except Exception as e:
            print(f"  ✗ Rate limit check failed: {type(e).__name__}")
            return False
    
    async def run_interactive_diagnosis(self) -> Dict[str, Any]:
        """Run interactive decision tree diagnosis."""
        print("\n🤖 Discord 530 Interactive Decision Tree")
        print("=" * 50)
        print("This tool will guide you through step-by-step troubleshooting.\n")
        
        current_node = self.tree
        path = []
        
        while current_node and not current_node.is_terminal:
            print(f"🔍 Checking: {current_node.question}")
            
            # Run the check function
            if current_node.check_function:
                try:
                    result = await current_node.check_function()
                    current_node.result = result
                    path.append({
                        "node": current_node.name,
                        "question": current_node.question,
                        "result": result
                    })
                    
                    # Decide next node based on result
                    if result:
                        current_node = current_node.yes_node
                    else:
                        current_node = current_node.no_node
                        
                except Exception as e:
                    print(f"  ✗ Check failed: {e}")
                    current_node = current_node.no_node
            else:
                # Manual decision node (shouldn't happen in this tree)
                response = input(f"{current_node.question} (y/n): ").lower().strip()
                result = response in ['y', 'yes', '1', 'true']
                current_node.result = result
                path.append({
                    "node": current_node.name,
                    "question": current_node.question,
                    "result": result
                })
                
                if result:
                    current_node = current_node.yes_node
                else:
                    current_node = current_node.no_node
            
            print()  # Add spacing
        
        # Save the path taken
        self.results["path"] = path
        
        # Show final solution
        if current_node:
            print("🎯 DIAGNOSIS COMPLETE")
            print("=" * 50)
            print(f"Root Cause: {current_node.name.replace('_', ' ').title()}")
            print("\n💡 Recommended Actions:")
            
            for i, action in enumerate(current_node.actions, 1):
                print(f"   {action}")
            
            self.results["recommendations"] = current_node.actions
        
        return self.results
    
    def save_results(self, filename: Optional[str] = None) -> str:
        """Save diagnosis results to file."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            filename = f"discord-530-decision-tree-{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        return filename
    
    def print_summary(self):
        """Print a summary of the diagnosis."""
        print("\n📋 DIAGNOSIS SUMMARY")
        print("=" * 50)
        
        findings = self.results["findings"]
        
        # Show key findings
        if "token_exists" in findings:
            status = "✓" if findings["token_exists"] else "✗"
            print(f"{status} Token exists: {findings['token_exists']}")
        
        if "token_valid" in findings:
            status = "✓" if findings["token_valid"] else "✗"
            print(f"{status} Token valid: {findings['token_valid']}")
        
        if "session_limits" in findings:
            limits = findings["session_limits"]
            remaining = limits.get("remaining", "?")
            total = limits.get("total", "?")
            print(f"📊 Session limits: {remaining}/{total} remaining")
        
        if "multiple_instances" in findings:
            instances = findings["multiple_instances"]
            python_count = instances.get("python_processes", 0)
            docker_count = instances.get("docker_containers", 0)
            print(f"🔄 Running instances: {python_count} Python, {docker_count} Docker")
        
        if "code_issues" in findings:
            issues = findings["code_issues"]
            if issues:
                print(f"⚠️  Code issues: {len(issues)} found")
        
        if "privileged_intents" in findings:
            intents = findings["privileged_intents"]
            if intents:
                print(f"🔐 Privileged intents: {', '.join(intents)}")
        
        if "network_connectivity" in findings:
            net = findings["network_connectivity"]
            api_ok = net.get("api_reachable", False)
            ws_ok = net.get("websocket_reachable", False)
            print(f"🌐 Network: API {api_ok}, WebSocket {ws_ok}")
        
        if "rate_limit_status" in findings:
            rate = findings["rate_limit_status"]
            if rate.get("is_rate_limited"):
                print("⏱️  Status: Rate limited")
            else:
                print("⏱️  Status: Not rate limited")


async def main():
    """Run the interactive decision tree."""
    tree = Discord530DecisionTree()
    
    try:
        results = await tree.run_interactive_diagnosis()
        
        # Print summary
        tree.print_summary()
        
        # Save results
        filename = tree.save_results()
        print(f"\n📁 Results saved to: {filename}")
        
        # Return appropriate exit code
        if tree.results.get("recommendations"):
            print("\n💡 Follow the recommended actions above to resolve the issue.")
            return 0
        else:
            print("\n❓ No specific recommendations could be determined.")
            print("Consider running the comprehensive diagnostic tool:")
            print("python scripts/diagnose-discord-530-comprehensive.py")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Diagnosis interrupted by user.")
        return 130
    except Exception as e:
        print(f"\n❌ Diagnosis failed: {e}")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)