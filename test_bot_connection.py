#!/usr/bin/env python3
import os
import asyncio
import discord
from discord.ext import commands

# Simple test bot to check Discord connection
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot connected successfully!')
    print(f'Bot name: {bot.user.name}')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} guilds')
    # Close after successful connection
    await bot.close()

@bot.event
async def on_error(event, *args, **kwargs):
    print(f'❌ Error in {event}: {args}')

async def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("No token found!")
        return
    
    print(f"Token length: {len(token)}")
    print("Attempting to connect to Discord...")
    
    try:
        await bot.start(token)
    except discord.LoginFailure as e:
        print(f"❌ Login failed: {e}")
    except Exception as e:
        print(f"❌ Connection error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())