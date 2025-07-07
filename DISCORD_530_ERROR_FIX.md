# Discord WebSocket 530 Error Fix Guide

## Problem Summary

Your Discord bot is experiencing WebSocket 530 errors when trying to connect to Discord gateways. This error occurs during the WebSocket handshake phase and indicates an **authentication failure** - your bot token is being rejected by Discord.

The errors you're seeing:
- `WebSocket handshake failed: 530 Invalid response status`
- `discord.errors.LoginFailure: Improper token has been passed`

## Root Cause

The WebSocket 530 error is Discord's way of rejecting invalid authentication during the gateway connection process. This happens when:

1. **Invalid Token**: The bot token is incorrect, expired, or has been regenerated
2. **Token Format Issues**: The token has extra characters, spaces, or the 'Bot ' prefix
3. **Revoked Token**: The bot was deleted or the token was manually revoked
4. **Rate Limiting**: Too many failed authentication attempts

## Immediate Solutions

### 1. Run the Diagnostic Tool
```bash
python scripts/diagnose-discord-auth.py
```
This will:
- Validate your token format
- Test API authentication
- Check gateway connectivity
- Provide specific recommendations

### 2. Run the Fix Script
```bash
python scripts/fix-discord-530-error.py
```
This will:
- Check your environment configuration
- Validate your token
- Apply automated fixes
- Provide step-by-step solutions

### 3. Regenerate Your Bot Token

This is the most likely solution:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Navigate to the "Bot" section
4. Click "Reset Token"
5. Copy the **entire** new token (it has 3 parts separated by dots)
6. Update your `.env` file:
   ```
   DISCORD_TOKEN=MTE3MzQx...GqvKbP.tj9wuWIH3e...
   ```
7. Do **NOT** include the 'Bot ' prefix - it's added automatically

### 4. Verify Token Format

A valid Discord bot token in 2025 should:
- Have 3 parts separated by dots
- Be approximately 70-80 characters long
- Look like: `MTE3MzQx...GqvKbP.tj9wuWIH3e...`
- NOT include 'Bot ' prefix in your .env file

## What I've Fixed

1. **Updated Network Connectivity Module** (`src/utils/network_connectivity.py`)
   - Added specific handling for WebSocket 530 errors
   - Provides clear error messages about authentication failures

2. **Enhanced Main Script** (`src/main.py`)
   - Added specific error handling for Discord login failures
   - Provides detailed instructions when authentication fails

3. **Created Diagnostic Tools**
   - `scripts/diagnose-discord-auth.py` - Comprehensive token and connection diagnostics
   - `scripts/fix-discord-530-error.py` - Automated fixes and solutions
   - `scripts/validate_token.py` - Quick token validation

4. **Created Enhanced Authentication Handler** (`src/utils/discord_auth_handler.py`)
   - Modern authentication handling for Discord in 2025
   - Token validation before connection attempts
   - Detailed error handling for all Discord error codes

## Testing Your Fix

After updating your token:

1. **Quick Token Test**:
   ```bash
   python scripts/validate_token.py
   ```

2. **Start Your Bot**:
   ```bash
   python -m src.main
   ```

3. **If Issues Persist**:
   ```bash
   python scripts/diagnose-discord-auth.py
   ```

## Common Mistakes to Avoid

1. **Including 'Bot ' prefix**: The token in .env should NOT have 'Bot ' prefix
2. **Partial token**: Ensure you copy the ENTIRE token from Discord
3. **Extra spaces**: Check for spaces or newlines in your token
4. **Old token**: If you regenerated the token, make sure you're using the new one
5. **Wrong token type**: Ensure it's a BOT token, not a user token

## Additional Considerations for 2025

Discord has updated their infrastructure and authentication requirements:

1. **API Version**: We're using API v10 (current standard)
2. **Gateway Version**: Using gateway v10 with JSON encoding
3. **Intents**: Ensure required intents are enabled in Developer Portal
4. **Session Limits**: Check if you've exhausted connection attempts

## VPS-Specific Issues

If running on a VPS:
- Some VPS providers block Discord connections
- Firewall rules might block WebSocket connections
- Check if your VPS IP is rate-limited by Discord

## Need More Help?

1. Check Discord Status: https://discordstatus.com
2. Review bot settings in Developer Portal
3. Ensure bot hasn't been removed from servers
4. Check for Discord API announcements

The diagnostic tools will provide specific guidance based on your situation. The 530 error is almost always a token issue, so regenerating your token is usually the solution.