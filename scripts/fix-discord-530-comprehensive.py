#!/usr/bin/env python3
"""
Discord 530 Error Comprehensive Fix Tool
Automated remediation based on investigation results

This script provides automated fixes for common causes of Discord 530 errors
when the token is confirmed valid. It can be run standalone or with investigation results.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import signal
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Color output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

@dataclass
class FixAction:
    name: str
    description: str
    commands: List[str]
    verification: Optional[str] = None
    risk_level: str = "low"  # low, medium, high
    requires_restart: bool = False

class Discord530FixTool:
    """Automated fix tool for Discord 530 errors"""
    
    def __init__(self):
        self.fixes_applied = []
        self.failed_fixes = []
        self.backup_created = False
        
    def print_header(self, text: str):
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")

    def print_section(self, text: str):
        print(f"\n{Colors.CYAN}{Colors.BOLD}🔧 {text}{Colors.ENDC}")

    def print_success(self, text: str):
        print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

    def print_warning(self, text: str):
        print(f"{Colors.YELLOW}⚠️ {text}{Colors.ENDC}")

    def print_error(self, text: str):
        print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

    def print_info(self, text: str):
        print(f"{Colors.BLUE}ℹ️ {text}{Colors.ENDC}")

    def run_command(self, command: str, timeout: int = 30) -> tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def create_backup(self):
        """Create backup of important configuration files"""
        if self.backup_created:
            return True
            
        backup_dir = Path(f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_dir.mkdir(exist_ok=True)
        
        files_to_backup = ['.env', 'config/config.yaml', 'docker-compose.yml']
        
        try:
            for file_path in files_to_backup:
                if os.path.exists(file_path):
                    dest = backup_dir / Path(file_path).name
                    subprocess.run(['cp', file_path, str(dest)], check=True)
                    
            self.print_success(f"Configuration backup created: {backup_dir}")
            self.backup_created = True
            return True
            
        except Exception as e:
            self.print_error(f"Failed to create backup: {e}")
            return False

    async def apply_fix(self, fix: FixAction, force: bool = False) -> bool:
        """Apply a specific fix action"""
        
        self.print_section(f"Applying Fix: {fix.name}")
        print(f"Description: {fix.description}")
        print(f"Risk Level: {fix.risk_level.upper()}")
        
        if fix.risk_level in ["medium", "high"] and not force:
            response = input(f"This fix has {fix.risk_level} risk. Continue? (y/N): ")
            if response.lower() != 'y':
                self.print_warning("Fix skipped by user")
                return False
                
        # Create backup for medium/high risk fixes
        if fix.risk_level in ["medium", "high"] and not self.backup_created:
            if not self.create_backup():
                self.print_error("Backup failed, aborting high-risk fix")
                return False
                
        # Execute fix commands
        success = True
        for i, command in enumerate(fix.commands, 1):
            print(f"  Step {i}/{len(fix.commands)}: {command}")
            
            exit_code, stdout, stderr = self.run_command(command)
            
            if exit_code == 0:
                self.print_success(f"Step {i} completed successfully")
                if stdout.strip():
                    print(f"    Output: {stdout.strip()}")
            else:
                self.print_error(f"Step {i} failed (exit code: {exit_code})")
                if stderr.strip():
                    print(f"    Error: {stderr.strip()}")
                success = False
                break
                
        # Verify fix if verification command provided
        if success and fix.verification:
            print(f"  Verifying fix: {fix.verification}")
            exit_code, stdout, stderr = self.run_command(fix.verification)
            
            if exit_code == 0:
                self.print_success("Fix verification passed")
            else:
                self.print_warning("Fix verification failed, but commands completed")
                
        if success:
            self.fixes_applied.append(fix.name)
            if fix.requires_restart:
                self.print_warning("This fix requires a bot restart to take effect")
        else:
            self.failed_fixes.append(fix.name)
            
        return success

    async def fix_session_limit_exhaustion(self) -> bool:
        """Fix session limit exhaustion issues"""
        
        fixes = [
            FixAction(
                name="Stop Multiple Bot Instances",
                description="Stop all running bot processes to free up sessions",
                commands=[
                    "pkill -f 'python.*main.py' || true",
                    "pkill -f 'python.*bot' || true", 
                    "docker-compose down || true",
                    "sleep 5"
                ],
                verification="! pgrep -f 'python.*main.py'",
                risk_level="medium",
                requires_restart=True
            ),
            FixAction(
                name="Wait for Session Reset",
                description="Wait for Discord session limits to reset",
                commands=[
                    "echo 'Waiting 60 seconds for session limits to reset...'",
                    "sleep 60"
                ],
                risk_level="low"
            ),
            FixAction(
                name="Clean Start Bot",
                description="Start bot with clean session state",
                commands=[
                    "docker-compose up -d --force-recreate"
                ],
                verification="docker-compose ps | grep -q 'running'",
                risk_level="low",
                requires_restart=False
            )
        ]
        
        success = True
        for fix in fixes:
            if not await self.apply_fix(fix):
                success = False
                break
                
        return success

    async def fix_token_issues(self) -> bool:
        """Fix token-related authentication issues"""
        
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            self.print_error("No DISCORD_TOKEN found in environment")
            return False
            
        fixes = []
        
        # Check for common token issues
        if token.startswith('Bot '):
            fixes.append(FixAction(
                name="Remove Bot Prefix",
                description="Remove 'Bot ' prefix from token",
                commands=[
                    f"sed -i 's/DISCORD_TOKEN=Bot /DISCORD_TOKEN=/' .env",
                    "echo 'Removed Bot prefix from token'"
                ],
                verification="! grep -q 'DISCORD_TOKEN=Bot ' .env",
                risk_level="low"
            ))
            
        if ' ' in token:
            fixes.append(FixAction(
                name="Remove Spaces from Token", 
                description="Remove spaces from token",
                commands=[
                    "sed -i 's/DISCORD_TOKEN=.*/DISCORD_TOKEN=" + token.replace(' ', '') + "/' .env",
                    "echo 'Removed spaces from token'"
                ],
                risk_level="low"
            ))
            
        # Token refresh guidance
        fixes.append(FixAction(
            name="Token Refresh Instructions",
            description="Display instructions for refreshing token",
            commands=[
                "echo '1. Go to https://discord.com/developers/applications'",
                "echo '2. Select your bot application'", 
                "echo '3. Go to Bot section'",
                "echo '4. Click Reset Token'",
                "echo '5. Copy the new token'",
                "echo '6. Update .env file: DISCORD_TOKEN=your-new-token'",
                "echo '7. Restart the bot'",
                "echo ''",
                "echo 'Token should be 59+ characters with no spaces or Bot prefix'"
            ],
            risk_level="low"
        ))
        
        success = True
        for fix in fixes:
            if not await self.apply_fix(fix):
                success = False
                
        return success

    async def fix_multiple_instances(self) -> bool:
        """Fix multiple bot instance conflicts"""
        
        fixes = [
            FixAction(
                name="Kill All Bot Processes",
                description="Terminate all Python bot processes",
                commands=[
                    "pkill -9 -f 'python.*main.py' || true",
                    "pkill -9 -f 'python.*bot' || true",
                    "pkill -9 -f 'discord' || true",
                    "sleep 3"
                ],
                verification="! pgrep -f 'python.*main.py'",
                risk_level="medium"
            ),
            FixAction(
                name="Stop Docker Containers",
                description="Stop all Docker containers to clear running instances",
                commands=[
                    "docker-compose down",
                    "docker stop $(docker ps -q) || true",
                    "sleep 5"
                ],
                verification="[ -z \"$(docker ps -q)\" ]",
                risk_level="medium"
            ),
            FixAction(
                name="Clean Docker Environment",
                description="Remove old containers and start fresh",
                commands=[
                    "docker-compose down --remove-orphans",
                    "docker container prune -f",
                    "docker-compose up -d --force-recreate"
                ],
                verification="docker-compose ps | grep -q 'running'",
                risk_level="medium"
            )
        ]
        
        success = True
        for fix in fixes:
            if not await self.apply_fix(fix):
                success = False
                break
                
        return success

    async def fix_network_issues(self) -> bool:
        """Fix network connectivity issues"""
        
        fixes = [
            FixAction(
                name="Fix DNS Configuration",
                description="Configure reliable DNS servers",
                commands=[
                    "echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf",
                    "echo 'nameserver 1.1.1.1' | sudo tee -a /etc/resolv.conf",
                    "sudo systemctl restart systemd-resolved || true"
                ],
                verification="ping -c 1 discord.com",
                risk_level="medium"
            ),
            FixAction(
                name="Restart Docker Networking",
                description="Restart Docker networking to fix connectivity",
                commands=[
                    "sudo systemctl restart docker",
                    "sleep 10",
                    "docker network prune -f"
                ],
                verification="docker network ls | grep -q bridge",
                risk_level="high"
            ),
            FixAction(
                name="Check Firewall Rules",
                description="Ensure outbound HTTPS is allowed",
                commands=[
                    "sudo ufw allow out 443/tcp || true",
                    "sudo ufw allow out 80/tcp || true",
                    "sudo ufw allow out 53 || true",
                    "sudo iptables -L OUTPUT | grep -q ACCEPT || sudo iptables -P OUTPUT ACCEPT"
                ],
                verification="curl -s https://discord.com > /dev/null",
                risk_level="high"
            )
        ]
        
        success = True
        for fix in fixes:
            if not await self.apply_fix(fix):
                # Network fixes are often environment-specific, so continue even if some fail
                self.print_warning(f"Network fix '{fix.name}' failed, but continuing...")
                
        return success

    async def fix_verification_issues(self) -> bool:
        """Address bot verification and guild limit issues"""
        
        fixes = [
            FixAction(
                name="Verification Guidance",
                description="Display bot verification guidance",
                commands=[
                    "echo 'Bot Verification Steps:'",
                    "echo '1. Go to Discord Developer Portal'",
                    "echo '2. Select your bot application'",
                    "echo '3. Navigate to Bot -> Public Bot section'",
                    "echo '4. If approaching 100 servers, apply for verification'",
                    "echo '5. Fill out verification form completely'",
                    "echo '6. Wait for Discord approval (can take weeks)'",
                    "echo ''",
                    "echo 'Temporary workarounds:'",
                    "echo '- Leave some servers to stay under 100'",
                    "echo '- Create a new bot application if needed'",
                    "echo '- Contact Discord support if verification was rejected'"
                ],
                risk_level="low"
            )
        ]
        
        for fix in fixes:
            await self.apply_fix(fix)
            
        return True

    async def fix_environment_issues(self) -> bool:
        """Fix environment and system resource issues"""
        
        fixes = [
            FixAction(
                name="Free Memory",
                description="Free up system memory",
                commands=[
                    "sudo sync",
                    "echo 1 | sudo tee /proc/sys/vm/drop_caches",
                    "docker system prune -f",
                    "pip cache purge || true"
                ],
                verification="free -m | awk 'NR==2{printf \"%.1f\", $3*100/$2}' | awk '{print ($1 < 80)}'",
                risk_level="medium"
            ),
            FixAction(
                name="Fix Docker Memory Limits", 
                description="Remove memory constraints that might cause issues",
                commands=[
                    "docker-compose down",
                    "sed -i '/mem_limit/d' docker-compose.yml || true",
                    "sed -i '/memory:/d' docker-compose.yml || true",
                    "docker-compose up -d"
                ],
                verification="docker-compose ps | grep -q 'running'",
                risk_level="medium"
            ),
            FixAction(
                name="Update System Packages",
                description="Update system packages for better compatibility",
                commands=[
                    "sudo apt update || sudo yum update -y || true",
                    "sudo apt upgrade -y ca-certificates openssl || sudo yum upgrade -y ca-certificates openssl || true"
                ],
                risk_level="medium"
            )
        ]
        
        success = True
        for fix in fixes:
            if not await self.apply_fix(fix):
                self.print_warning(f"Environment fix '{fix.name}' failed, continuing...")
                
        return success

    async def fix_code_configuration(self) -> bool:
        """Fix common code and configuration issues"""
        
        fixes = [
            FixAction(
                name="Update Discord.py",
                description="Update to latest discord.py version",
                commands=[
                    "pip install --upgrade discord.py",
                    "pip install --upgrade aiohttp"
                ],
                verification="python -c 'import discord; print(discord.__version__)'",
                risk_level="low"
            ),
            FixAction(
                name="Fix Environment Variables",
                description="Ensure required environment variables are properly set",
                commands=[
                    "grep -q '^DISCORD_TOKEN=' .env || echo 'DISCORD_TOKEN=YOUR_TOKEN_HERE' >> .env",
                    "grep -q '^LOG_LEVEL=' .env || echo 'LOG_LEVEL=INFO' >> .env",
                    "chmod 600 .env"
                ],
                verification="[ -f .env ] && grep -q DISCORD_TOKEN .env",
                risk_level="low"
            ),
            FixAction(
                name="Reset Configuration",
                description="Reset to default configuration if available",
                commands=[
                    "cp config/config.yaml.example config/config.yaml || true",
                    "cp .env.example .env.backup || true",
                    "echo 'Configuration reset to defaults'"
                ],
                risk_level="medium"
            )
        ]
        
        success = True
        for fix in fixes:
            if not await self.apply_fix(fix):
                self.print_warning(f"Configuration fix '{fix.name}' failed, continuing...")
                
        return success

    async def run_guided_fixes(self):
        """Run guided fix process based on user selection"""
        
        self.print_header("Discord 530 Error Guided Fix Tool")
        
        print("This tool will help fix common causes of Discord 530 errors.")
        print("Fixes are organized by likely cause and risk level.")
        
        fix_categories = {
            "1": ("Session Limit Exhaustion", self.fix_session_limit_exhaustion),
            "2": ("Token Authentication Issues", self.fix_token_issues), 
            "3": ("Multiple Bot Instances", self.fix_multiple_instances),
            "4": ("Network Connectivity Issues", self.fix_network_issues),
            "5": ("Bot Verification Issues", self.fix_verification_issues),
            "6": ("Environment/System Issues", self.fix_environment_issues),
            "7": ("Code Configuration Issues", self.fix_code_configuration)
        }
        
        print("\nAvailable fix categories:")
        for key, (name, _) in fix_categories.items():
            print(f"  {key}. {name}")
        print("  8. Run all fixes (recommended)")
        print("  9. Exit")
        
        while True:
            choice = input("\nSelect fix category (1-9): ").strip()
            
            if choice == "9":
                print("Exiting fix tool")
                break
            elif choice == "8":
                print("\nRunning all fixes...")
                for name, fix_func in fix_categories.values():
                    self.print_section(f"Running {name}")
                    try:
                        await fix_func()
                    except Exception as e:
                        self.print_error(f"Fix category failed: {e}")
                break
            elif choice in fix_categories:
                name, fix_func = fix_categories[choice]
                self.print_section(f"Running {name}")
                try:
                    success = await fix_func()
                    if success:
                        self.print_success(f"{name} completed successfully")
                    else:
                        self.print_warning(f"{name} completed with issues")
                except Exception as e:
                    self.print_error(f"Fix failed: {e}")
                    
                # Ask if user wants to continue
                continue_choice = input("\nTry another fix category? (y/n): ").strip().lower()
                if continue_choice != 'y':
                    break
            else:
                print("Invalid choice, please select 1-9")

    async def run_automated_fixes(self, investigation_file: Optional[str] = None):
        """Run automated fixes based on investigation results"""
        
        self.print_header("Discord 530 Error Automated Fix Tool")
        
        # Load investigation results if provided
        root_cause = None
        if investigation_file and os.path.exists(investigation_file):
            try:
                with open(investigation_file, 'r') as f:
                    results = json.load(f)
                    analysis = results.get('analysis', {})
                    root_cause = analysis.get('likely_root_cause')
                    
                self.print_success(f"Loaded investigation results: {investigation_file}")
                self.print_info(f"Identified root cause: {root_cause}")
                
            except Exception as e:
                self.print_warning(f"Could not load investigation results: {e}")
                
        # Apply fixes based on identified root cause
        if root_cause == "session_limit_exhausted":
            self.print_section("Fixing Session Limit Exhaustion")
            await self.fix_session_limit_exhaustion()
            
        elif root_cause == "token_invalid_or_revoked":
            self.print_section("Fixing Token Issues")
            await self.fix_token_issues()
            
        elif root_cause == "multiple_bot_instances":
            self.print_section("Fixing Multiple Instance Conflicts")
            await self.fix_multiple_instances()
            
        elif root_cause == "network_connectivity_issues":
            self.print_section("Fixing Network Issues")
            await self.fix_network_issues()
            
        elif root_cause == "bot_verification_or_limits":
            self.print_section("Addressing Verification Issues")
            await self.fix_verification_issues()
            
        else:
            # Run comprehensive fixes
            self.print_section("Running Comprehensive Fix Suite")
            self.print_info("No specific root cause identified, running all fixes...")
            
            await self.fix_session_limit_exhaustion()
            await self.fix_multiple_instances() 
            await self.fix_network_issues()
            await self.fix_environment_issues()
            await self.fix_code_configuration()

    def print_summary(self):
        """Print summary of applied fixes"""
        
        self.print_header("Fix Summary")
        
        if self.fixes_applied:
            self.print_success(f"Successfully applied {len(self.fixes_applied)} fixes:")
            for fix in self.fixes_applied:
                print(f"  ✅ {fix}")
                
        if self.failed_fixes:
            self.print_warning(f"Failed to apply {len(self.failed_fixes)} fixes:")
            for fix in self.failed_fixes:
                print(f"  ❌ {fix}")
                
        if not self.fixes_applied and not self.failed_fixes:
            self.print_info("No fixes were applied")
            
        print("\nNext steps:")
        print("1. Restart your bot if any fixes require it")
        print("2. Monitor bot logs for any remaining issues")
        print("3. Run the investigation tool again if problems persist")
        print("4. Check Discord Developer Portal for any account issues")


async def main():
    """Main function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Discord 530 Error Fix Tool")
    parser.add_argument("--investigation", help="Path to investigation results JSON file")
    parser.add_argument("--guided", action="store_true", help="Run guided fix process")
    parser.add_argument("--automated", action="store_true", help="Run automated fixes")
    parser.add_argument("--force", action="store_true", help="Force apply all fixes without prompts")
    
    args = parser.parse_args()
    
    fix_tool = Discord530FixTool()
    
    try:
        if args.guided or (not args.automated and not args.investigation):
            await fix_tool.run_guided_fixes()
        else:
            await fix_tool.run_automated_fixes(args.investigation)
            
        fix_tool.print_summary()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️ Fix process interrupted by user{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Unexpected error during fix process: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())