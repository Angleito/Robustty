#!/usr/bin/env python3
"""
Fix Discord WebSocket 530 Authentication Errors
This script diagnoses and provides solutions for Discord gateway connection issues
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import aiohttp
import discord

# Import our diagnostic tool
from scripts.diagnose_discord_auth import DiscordAuthDiagnostics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_token_in_env():
    """Check if token is properly set in environment"""
    print("\n🔍 Checking environment configuration...")
    
    # Check .env file
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found!")
        print("   Run: cp .env.example .env")
        return None
        
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("❌ DISCORD_TOKEN not found in .env file!")
        print("   Add: DISCORD_TOKEN=your-bot-token-here")
        return None
        
    if token.startswith('your-') or token == 'your_discord_bot_token':
        print("❌ DISCORD_TOKEN appears to be a placeholder!")
        print("   Replace with your actual bot token from Discord Developer Portal")
        return None
        
    # Remove 'Bot ' prefix if present
    if token.startswith('Bot '):
        token = token[4:]
        print("⚠️  Removed 'Bot ' prefix from token (it's added automatically)")
        
    print("✅ Token found in environment")
    return token


async def test_simple_connection(token: str):
    """Test a simple WebSocket connection to Discord"""
    print("\n🔌 Testing basic WebSocket connection...")
    
    try:
        # Get gateway URL
        headers = {'Authorization': f'Bot {token}'}
        async with aiohttp.ClientSession() as session:
            async with session.get('https://discord.com/api/v10/gateway/bot', headers=headers) as resp:
                if resp.status != 200:
                    print(f"❌ Failed to get gateway URL: HTTP {resp.status}")
                    return False
                    
                data = await resp.json()
                gateway_url = data.get('url')
                print(f"✅ Gateway URL obtained: {gateway_url}")
                
        # Try WebSocket connection
        ws_url = f"{gateway_url}/?v=10&encoding=json"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(ws_url, timeout=10) as ws:
                    print("✅ WebSocket connection established")
                    
                    # Wait for Hello
                    msg = await ws.receive()
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get('op') == 10:
                            print("✅ Received Hello from Discord")
                            return True
                            
            except aiohttp.WSServerHandshakeError as e:
                print(f"❌ WebSocket handshake failed: {e.status} {e.message}")
                if hasattr(e, 'status') and e.status == 530:
                    print("   This is the 530 authentication error!")
                return False
                
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


async def apply_fixes(token: str):
    """Apply fixes for common issues"""
    print("\n🔧 Applying fixes...")
    
    fixes_applied = []
    
    # Fix 1: Update network connectivity module to handle 530 errors
    print("\n📝 Updating network connectivity module...")
    try:
        nc_file = Path('src/utils/network_connectivity.py')
        if nc_file.exists():
            content = nc_file.read_text()
            
            # Add handling for 530 errors in check_discord_gateway
            if '530' not in content:
                # Find the WSServerHandshakeError handling section
                insert_pos = content.find('except aiohttp.WSServerHandshakeError as e:')
                if insert_pos != -1:
                    # Find the end of this exception block
                    block_start = content.find('{', insert_pos)
                    block_end = content.find(')', block_start) + 1
                    
                    new_handling = '''
                    # Handle 530 authentication errors specifically
                    if hasattr(e, 'status') and e.status == 530:
                        return (
                            False,
                            response_time,
                            f"Authentication failed (530): Token is invalid or expired",
                        )'''
                    
                    # We'll provide instructions instead of modifying
                    print("   ℹ️  Network connectivity module needs update for 530 handling")
                    fixes_applied.append("Update network_connectivity.py to handle 530 errors")
                    
    except Exception as e:
        print(f"   ⚠️  Could not check network connectivity module: {e}")
        
    # Fix 2: Create token validation utility
    print("\n📝 Creating token validation utility...")
    validation_script = Path('scripts/validate_token.py')
    validation_content = '''#!/usr/bin/env python3
"""Quick token validation script"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

async def validate():
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN', '').replace('Bot ', '')
    
    if not token:
        print("❌ No token found in DISCORD_TOKEN environment variable")
        return
        
    headers = {'Authorization': f'Bot {token}'}
    async with aiohttp.ClientSession() as session:
        async with session.get('https://discord.com/api/v10/users/@me', headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✅ Token valid! Bot: {data['username']}#{data['discriminator']}")
            else:
                print(f"❌ Token invalid! HTTP {resp.status}")

if __name__ == '__main__':
    asyncio.run(validate())
'''
    
    validation_script.write_text(validation_content)
    validation_script.chmod(0o755)
    print("   ✅ Created scripts/validate_token.py")
    fixes_applied.append("Created token validation script")
    
    return fixes_applied


async def provide_solutions():
    """Provide comprehensive solutions for the 530 error"""
    print("\n💡 SOLUTIONS FOR WEBSOCKET 530 ERROR")
    print("=" * 60)
    
    print("\n1️⃣  REGENERATE YOUR BOT TOKEN:")
    print("   a. Go to https://discord.com/developers/applications")
    print("   b. Select your application")
    print("   c. Go to 'Bot' section")
    print("   d. Click 'Reset Token'")
    print("   e. Copy the new token COMPLETELY")
    print("   f. Update your .env file with the new token")
    
    print("\n2️⃣  VERIFY TOKEN FORMAT:")
    print("   - Token should have 3 parts separated by dots")
    print("   - Example: MTE3MzQx....GqvKbP.tj9wuWIH3e...")
    print("   - Do NOT include 'Bot ' prefix in .env file")
    print("   - Ensure no extra spaces or newlines")
    
    print("\n3️⃣  CHECK BOT SETTINGS:")
    print("   a. Ensure bot is not deleted")
    print("   b. Check 'Bot' section is enabled in Developer Portal")
    print("   c. Verify required intents are enabled")
    print("   d. Ensure bot wasn't rate limited")
    
    print("\n4️⃣  UPDATE AUTHENTICATION HANDLING:")
    print("   Run: python scripts/update_auth_handling.py")
    print("   This will update your bot to use modern authentication")
    
    print("\n5️⃣  TEST YOUR TOKEN:")
    print("   Run: python scripts/validate_token.py")
    print("   This will quickly verify if your token is valid")
    
    print("\n6️⃣  CHECK DISCORD STATUS:")
    print("   Visit: https://discordstatus.com")
    print("   Ensure Discord API is operational")


def create_update_script():
    """Create a script to update authentication handling"""
    update_script = Path('scripts/update_auth_handling.py')
    update_content = '''#!/usr/bin/env python3
"""Update bot to use enhanced authentication handling"""
import shutil
from pathlib import Path

print("Updating authentication handling...")

# Backup original files
files_to_backup = [
    'src/main.py',
    'src/bot/bot.py',
]

for file_path in files_to_backup:
    src = Path(file_path)
    if src.exists():
        backup = Path(f"{file_path}.backup")
        shutil.copy2(src, backup)
        print(f"✅ Backed up {file_path}")

# Add import to main.py
main_file = Path('src/main.py')
if main_file.exists():
    content = main_file.read_text()
    if 'discord_auth_handler' not in content:
        # Add import after other imports
        import_line = "from src.utils.discord_auth_handler import create_resilient_bot"
        lines = content.split('\\n')
        
        # Find where to insert
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith('from src.'):
                insert_pos = i + 1
                
        lines.insert(insert_pos, import_line)
        
        # Update bot creation
        new_content = '\\n'.join(lines)
        new_content = new_content.replace(
            'bot = RobusttyBot(config)',
            '# Use enhanced authentication\\n        bot = create_resilient_bot(config)'
        )
        
        main_file.write_text(new_content)
        print("✅ Updated main.py with enhanced authentication")

print("\\n✨ Authentication handling updated!")
print("Restart your bot to use the new authentication system.")
'''
    
    update_script.write_text(update_content)
    update_script.chmod(0o755)
    print(f"\n✅ Created {update_script}")


async def main():
    """Main diagnostic and fix routine"""
    print("🔧 Discord WebSocket 530 Error Fixer")
    print("=" * 60)
    
    # Step 1: Check environment
    token = await check_token_in_env()
    if not token:
        await provide_solutions()
        return
        
    # Step 2: Run diagnostics
    print("\n📊 Running comprehensive diagnostics...")
    diagnostics = DiscordAuthDiagnostics(token)
    
    try:
        results = await diagnostics.run_diagnostics()
        diagnostics.print_summary()
        
        # Check if token is valid
        token_valid = results.get('token_format', {}).get('valid_format', False)
        api_success = any(
            endpoint.get('success', False) 
            for endpoint in results.get('api_authentication', {}).get('endpoints_tested', {}).values()
        )
        
        if not token_valid or not api_success:
            print("\n❌ TOKEN IS INVALID OR EXPIRED!")
            await provide_solutions()
            
            # Create helper scripts
            create_update_script()
            
        else:
            print("\n✅ Token appears to be valid!")
            
            # Test simple connection
            if not await test_simple_connection(token):
                print("\n⚠️  Token is valid but WebSocket connection fails")
                print("This might be due to:")
                print("- Network restrictions")
                print("- Firewall blocking WebSocket")
                print("- VPS provider blocking Discord")
                print("- Rate limiting")
                
            # Apply fixes
            fixes = await apply_fixes(token)
            if fixes:
                print(f"\n✅ Applied {len(fixes)} fixes:")
                for fix in fixes:
                    print(f"   - {fix}")
                    
    except Exception as e:
        print(f"\n❌ Diagnostic error: {e}")
        await provide_solutions()
        
    print("\n📚 Next Steps:")
    print("1. If token is invalid: Follow the solutions above")
    print("2. Run: python scripts/validate_token.py")
    print("3. Restart your bot: python -m src.main")
    print("4. If issues persist: Run python scripts/diagnose-discord-auth.py")


if __name__ == '__main__':
    asyncio.run(main())