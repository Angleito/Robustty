# Discord Gateway 530 Error Fix Summary - July 2025

## Root Cause
The WebSocket 530 errors are caused by **invalid Discord bot token**. Discord is rejecting your authentication before the WebSocket handshake can complete.

## Immediate Solution

### 1. Get a Valid Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application (or create a new one)
3. Navigate to the **Bot** section in the left sidebar
4. Click **Reset Token** button
5. Copy the entire token (it will look like: `MTEyMzQ1Njc4OTAxMjM0NTY3OA.GAbcde.1234567890abcdefghijklmnop`)

### 2. Update Your .env File

```bash
# Edit .env file
nano .env

# Update this line:
DISCORD_TOKEN=your_actual_token_here

# Important: Do NOT include 'Bot ' prefix
# ❌ Wrong: DISCORD_TOKEN=Bot MTEyMzQ1Njc4OTAxMjM0NTY3OA.GAbcde.1234567890abcdefghijklmnop
# ✅ Right: DISCORD_TOKEN=MTEyMzQ1Njc4OTAxMjM0NTY3OA.GAbcde.1234567890abcdefghijklmnop
```

### 3. Restart Your Bot

```bash
# Stop and restart containers
docker-compose down
docker-compose up -d

# Monitor logs
docker logs -f robustty-bot
```

## Why This Happens

- **530 Error**: This is a Cloudflare error indicating DNS/origin issues
- **In Discord's Context**: It means authentication failed before WebSocket handshake
- **Regional Gateways**: These return 530 when authentication fails
- **Solution**: The bot has been configured to use the main gateway only

## Verification

After updating your token, you should see:
```
INFO:discord.client:Shard ID 0 has connected to Gateway (Session ID: ...)
Bot ready! Logged in as YourBotName#1234
```

## Additional Fixes Applied

1. **DNS Configuration**: Added multiple DNS servers for reliability
2. **Gateway Configuration**: Bot now uses main gateway.discord.gg only
3. **Network Fixes**: Created scripts for VPS network troubleshooting
4. **Cookie Conversion**: Added automatic Netscape to JSON cookie conversion

## Still Having Issues?

Run diagnostics:
```bash
python scripts/fix-discord-gateway-2025.py
```

The 530 errors will disappear once you have a valid Discord token!