# Discord Intents Verification Guide

## Overview

Robustty requires specific Discord privileged intents to function properly. The diagnostic has detected that your bot uses `message_content` intent, which requires special permission from Discord.

## Required Intents for Robustty

Based on the bot configuration in `/src/bot/bot.py`, Robustty requires:

```python
intents = discord.Intents.default()
intents.message_content = True  # ⚠️ PRIVILEGED INTENT
intents.voice_states = True     # ✅ Standard intent
```

## Privileged Intents Verification Steps

### 1. Access Discord Developer Portal

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Log in with your Discord account
3. Select your bot application from the list

### 2. Navigate to Bot Settings

1. Click on "Bot" in the left sidebar
2. Scroll down to the "Privileged Gateway Intents" section

### 3. Enable Required Privileged Intents

Enable the following privileged intents:

#### ✅ Message Content Intent
- **Setting**: "Message Content Intent"
- **Required**: YES
- **Reason**: Robustty needs to read message content to process music commands
- **Impact if disabled**: Bot cannot read command messages or respond to user requests

#### ❓ Server Members Intent (Optional)
- **Setting**: "Server Members Intent" 
- **Required**: NO (for basic functionality)
- **Reason**: Only needed for advanced member management features
- **Impact if disabled**: Limited member-related functionality

#### ❓ Presence Intent (Optional)
- **Setting**: "Presence Intent"
- **Required**: NO (for basic functionality)
- **Reason**: Only needed to detect user online status
- **Impact if disabled**: Cannot detect user presence for advanced features

### 4. Save Changes

1. Click "Save Changes" at the bottom of the page
2. Wait for Discord to confirm the changes

### 5. Bot Verification Requirements

⚠️ **Important**: If your bot is in 100+ servers, Discord requires verification for privileged intents:

- **Under 100 servers**: Privileged intents can be enabled immediately
- **100+ servers**: Requires Discord verification process (can take several weeks)

## Verification Checklist

Use this checklist to verify your bot's intent configuration:

### In Discord Developer Portal:
- [ ] Message Content Intent is ENABLED
- [ ] Bot token is regenerated after intent changes (recommended)
- [ ] Bot permissions include "Send Messages", "Read Message History", "Connect", "Speak"

### In Bot Configuration:
- [ ] `DISCORD_TOKEN` environment variable is up to date
- [ ] Bot is invited to server with correct permissions
- [ ] Bot has necessary channel permissions (read/send messages in command channels)

### Testing:
- [ ] Bot responds to basic commands (e.g., `!help`, `!ping`)
- [ ] Bot can join voice channels
- [ ] Bot can play audio successfully
- [ ] No "missing intents" errors in logs

## Common Issues and Solutions

### Issue: Bot doesn't respond to commands
**Cause**: Message Content Intent not enabled
**Solution**: Enable "Message Content Intent" in Developer Portal

### Issue: "403 Forbidden" errors
**Cause**: Missing bot permissions in server
**Solution**: Re-invite bot with proper permissions using invite link generator

### Issue: "Gateway error" or "Intents" errors in logs
**Cause**: Mismatch between code intents and portal settings
**Solution**: Ensure portal settings match the intents defined in code

### Issue: Bot works in small servers but not large ones
**Cause**: Large servers (100+) require verified intents
**Solution**: Submit bot for Discord verification or reduce server count

## Intent Configuration Commands

### Check Current Intents (for debugging):
```python
# Add this to a command for debugging
@bot.command()
async def check_intents(ctx):
    intents = bot.intents
    await ctx.send(f"Message Content: {intents.message_content}")
    await ctx.send(f"Voice States: {intents.voice_states}")
    await ctx.send(f"Guild Members: {intents.members}")
```

### Environment Variables Check:
```bash
# Verify your Discord token is set
echo $DISCORD_TOKEN

# Check if token starts with the correct prefix
# Bot tokens should start with MTxxxxxxx or similar
```

## Bot Permissions Required

In addition to intents, ensure your bot has these permissions in Discord servers:

### Text Permissions:
- Send Messages
- Read Message History  
- Use Slash Commands (if applicable)
- Embed Links
- Attach Files

### Voice Permissions:
- Connect
- Speak
- Use Voice Activity
- Priority Speaker (optional)

## Troubleshooting Commands

Run these commands to diagnose intent-related issues:

```bash
# Check bot logs for intent errors
docker-compose logs robustty | grep -i "intent\|gateway\|403"

# Test Discord connectivity
python -c "
import discord
import os
intents = discord.Intents.default()
intents.message_content = True
print('Intents configured:', intents)
"

# Validate Discord token format
python -c "
import os
token = os.getenv('DISCORD_TOKEN', '')
if token:
    print('Token length:', len(token))
    print('Token prefix:', token[:10] + '...')
else:
    print('ERROR: DISCORD_TOKEN not set')
"
```

## Resources

- [Discord Intents Documentation](https://discord.com/developers/docs/topics/gateway#gateway-intents)
- [Discord Privileged Intents Guide](https://support.discord.com/hc/en-us/articles/360040720412)
- [Discord Bot Verification Process](https://support.discord.com/hc/en-us/articles/360040720412-Bot-Verification-and-Data-Whitelisting)

## Support

If you continue to experience intent-related issues:

1. Check the [Discord Developer Portal](https://discord.com/developers/applications) settings
2. Review bot logs for specific error messages
3. Test with a fresh bot token if needed
4. Ensure your `.env` file has the correct `DISCORD_TOKEN`