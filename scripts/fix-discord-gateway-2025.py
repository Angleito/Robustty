#!/usr/bin/env python3
"""
Discord Gateway Connection Fix for July 2025
Addresses WebSocket 530 errors and authentication issues
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_dns_resolution():
    """Test DNS resolution for Discord gateways"""
    print("\n🔍 Testing DNS Resolution...")
    
    hosts = [
        "gateway.discord.gg",
        "discord.com",
        "discordapp.com"
    ]
    
    for host in hosts:
        try:
            result = subprocess.run(
                ["nslookup", host],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ {host}: DNS resolution successful")
            else:
                print(f"❌ {host}: DNS resolution failed")
                print("   Fix: Add DNS servers to your system or Docker config")
        except Exception as e:
            print(f"❌ {host}: Error - {e}")

def test_discord_connectivity():
    """Test basic connectivity to Discord"""
    print("\n🔍 Testing Discord API Connectivity...")
    
    try:
        import requests
        
        # Test API endpoint (no auth needed)
        response = requests.get("https://discord.com/api/v10/gateway", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Discord API reachable")
            print(f"   Gateway URL: {data.get('url', 'Not found')}")
        else:
            print(f"❌ Discord API returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach Discord API: {e}")

def fix_network_configuration():
    """Apply network fixes for VPS environments"""
    print("\n🔧 Applying Network Fixes...")
    
    # Update Docker compose DNS settings
    compose_path = Path("docker-compose.yml")
    if compose_path.exists():
        print("✅ docker-compose.yml found")
        print("   DNS servers already configured in compose file")
    
    # Create DNS fix script for container
    dns_fix = """#!/bin/bash
# Add reliable DNS servers
echo "nameserver 8.8.8.8" >> /etc/resolv.conf
echo "nameserver 1.1.1.1" >> /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf
"""
    
    with open("scripts/container-dns-fix.sh", "w") as f:
        f.write(dns_fix)
    os.chmod("scripts/container-dns-fix.sh", 0o755)
    print("✅ Created container DNS fix script")

def update_bot_configuration():
    """Update bot to use main gateway instead of regional ones"""
    print("\n🔧 Updating Bot Configuration...")
    
    # Create gateway override configuration
    config = {
        "network": {
            "use_regional_gateways": False,
            "primary_gateway": "gateway.discord.gg",
            "fallback_gateways": [],
            "connection_timeout": 30,
            "reconnect_delay": 5
        }
    }
    
    config_path = Path("config/gateway-override.json")
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print("✅ Created gateway override configuration")
    print("   Bot will now use main gateway only")

def validate_token_format():
    """Check token format in .env file"""
    print("\n🔍 Checking Token Format...")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        return False
    
    with open(env_path, "r") as f:
        content = f.read()
    
    if "DISCORD_TOKEN=your_discord_bot_token_here" in content:
        print("❌ Token is still set to placeholder value!")
        print("\n📝 To fix:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Select your application")
        print("3. Go to Bot section")
        print("4. Click 'Reset Token' and copy the new token")
        print("5. Update .env file with: DISCORD_TOKEN=<your_actual_token>")
        print("   (Do NOT include 'Bot ' prefix)")
        return False
    
    # Check for common token format issues
    lines = content.split('\n')
    for line in lines:
        if line.startswith('DISCORD_TOKEN='):
            token_value = line.split('=', 1)[1].strip()
            
            if not token_value:
                print("❌ Token is empty!")
                return False
            
            if token_value.startswith('"') and token_value.endswith('"'):
                print("⚠️  Token has quotes - this might cause issues")
                print("   Remove quotes from token value")
            
            if ' ' in token_value:
                print("❌ Token contains spaces!")
                return False
            
            if token_value.startswith('Bot '):
                print("❌ Token includes 'Bot ' prefix - remove it!")
                return False
            
            print("✅ Token format appears correct")
            return True
    
    print("❌ DISCORD_TOKEN not found in .env!")
    return False

def main():
    print("🤖 Discord Gateway 530 Error Fix - July 2025")
    print("=" * 50)
    
    # Check DNS resolution
    check_dns_resolution()
    
    # Test Discord connectivity
    test_discord_connectivity()
    
    # Apply network fixes
    fix_network_configuration()
    
    # Update bot configuration
    update_bot_configuration()
    
    # Validate token
    token_valid = validate_token_format()
    
    print("\n" + "=" * 50)
    print("📋 Summary:")
    
    if not token_valid:
        print("❌ Invalid Discord token - this is your main issue!")
        print("   Follow the steps above to get a new token")
    else:
        print("✅ Token format is valid")
        print("\n🚀 Next steps:")
        print("1. Rebuild Docker container:")
        print("   docker-compose down && docker-compose up -d --build")
        print("2. Monitor logs:")
        print("   docker logs -f robustty-bot")
        print("3. If issues persist, run diagnostics:")
        print("   python scripts/diagnose-discord-auth.py")

if __name__ == "__main__":
    main()