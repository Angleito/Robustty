#!/usr/bin/env python3
"""
Network DNS fix utility for Robustty bot.

This script configures the system to use reliable DNS servers
and provides network configuration recommendations.
"""

import os
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_dns_config():
    """Check current DNS configuration"""
    try:
        # Check current DNS settings
        result = subprocess.run(['scutil', '--dns'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Current DNS configuration:")
            print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
        
        # Check resolver config
        if os.path.exists('/etc/resolv.conf'):
            logger.info("Current /etc/resolv.conf:")
            with open('/etc/resolv.conf', 'r') as f:
                print(f.read()[:200])
    except Exception as e:
        logger.warning(f"Could not check DNS config: {e}")


def suggest_dns_fixes():
    """Suggest DNS configuration fixes"""
    print("\n🔧 RECOMMENDED DNS FIXES:")
    print("=" * 50)
    
    print("\n1. 🖥️  SYSTEM LEVEL (macOS):")
    print("   ➤ System Preferences → Network → Advanced → DNS")
    print("   ➤ Add DNS servers: 1.1.1.1, 8.8.8.8, 9.9.9.9")
    print("   ➤ Click OK and Apply")
    
    print("\n2. 🌐 ROUTER LEVEL:")
    print("   ➤ Access router admin (usually 192.168.1.1 or 192.168.8.1)")
    print("   ➤ Change DNS settings to: 1.1.1.1, 8.8.8.8")
    print("   ➤ This affects all devices on the network")
    
    print("\n3. 🐳 DOCKER LEVEL:")
    print("   ➤ Add to docker-compose.yml:")
    print("     services:")
    print("       robustty:")
    print("         dns:")
    print("           - 1.1.1.1")
    print("           - 8.8.8.8")
    
    print("\n4. 🤖 APPLICATION LEVEL:")
    print("   ➤ The bot is already configured to use multiple DNS servers")
    print("   ➤ It will fallback to public DNS if system DNS fails")
    
    print("\n5. 🧹 FLUSH DNS CACHE:")
    print("   ➤ Run: sudo dscacheutil -flushcache")
    print("   ➤ Run: sudo killall -HUP mDNSResponder")


def test_specific_resolutions():
    """Test specific problematic domains"""
    print("\n🔍 TESTING SPECIFIC DOMAIN RESOLUTIONS:")
    print("=" * 50)
    
    problematic_domains = [
        "gateway-us-west-1.discord.gg",
        "gateway-us-east-1.discord.gg", 
        "peertube.social",
        "gateway.discord.gg",  # This should work
    ]
    
    dns_servers = ["8.8.8.8", "1.1.1.1"]
    
    for domain in problematic_domains:
        print(f"\n🔍 Testing {domain}:")
        
        for dns in dns_servers:
            try:
                result = subprocess.run(
                    ['nslookup', domain, dns], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode == 0 and 'NXDOMAIN' not in result.stdout:
                    # Extract IP addresses
                    lines = result.stdout.split('\n')
                    addresses = [line.split()[-1] for line in lines if 'Address:' in line and '#53' not in line]
                    if addresses:
                        print(f"  ✅ {dns}: {', '.join(addresses)}")
                    else:
                        print(f"  ✅ {dns}: Resolved (no addresses shown)")
                else:
                    print(f"  ❌ {dns}: Failed to resolve")
                    
            except subprocess.TimeoutExpired:
                print(f"  ⏰ {dns}: Timeout")
            except Exception as e:
                print(f"  ❌ {dns}: Error - {e}")


def main():
    """Main function"""
    print("🔧 ROBUSTTY DNS CONFIGURATION UTILITY")
    print("=" * 50)
    
    # Check current DNS configuration
    check_dns_config()
    
    # Test specific problematic domains
    test_specific_resolutions()
    
    # Provide recommendations
    suggest_dns_fixes()
    
    print("\n✅ NEXT STEPS:")
    print("=" * 20)
    print("1. Apply one or more DNS fixes above")
    print("2. Restart the bot")
    print("3. Run: ./scripts/simple-network-check.sh")
    print("4. Check bot logs for improved connectivity")


if __name__ == "__main__":
    main()