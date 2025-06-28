"""
Enhanced Discord Connection Handler with WebSocket Code 1000 Resilience

Based on 2024 best practices for Discord WebSocket reconnection issues.
Implements proper session management, exponential backoff, and rate limiting protection.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class DiscordConnectionHandler:
    """Enhanced connection handler for Discord WebSocket resilience"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reconnect_attempts = 0
        self.last_disconnect_time = 0
        self.session_id: Optional[str] = None
        self.sequence_number: Optional[int] = None
        self.heartbeat_failures = 0
        self.rate_limit_reset_time = 0
        
        # Enhanced reconnection settings
        self.base_delay = 6.0  # Discord requires 6 seconds minimum, not 5
        self.max_delay = 300.0  # 5 minutes maximum
        self.max_attempts = 10
        
        # Rate limiting protection
        self.last_status_change = 0
        self.status_change_cooldown = 20.0  # 20 second cooldown between status changes
    
    async def handle_disconnect(self, code: int, reason: str = "") -> None:
        """Handle WebSocket disconnection with proper reconnection logic"""
        self.last_disconnect_time = time.time()
        self.reconnect_attempts += 1
        
        logger.warning(f"Discord WebSocket disconnected with code {code}: {reason}")
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_attempts}")
        
        # Handle specific close codes
        if code == 1000:  # Normal closure - often indicates Discord-initiated reconnection
            logger.info("Code 1000: Normal closure - Discord may have requested reconnection")
            await self._handle_normal_closure()
        elif code == 4006:  # Invalid session
            logger.warning("Code 4006: Invalid session - need to re-identify")
            self.session_id = None
            self.sequence_number = None
        elif code == 4008:  # Rate limited
            logger.error("Code 4008: Rate limited - implementing longer backoff")
            self.rate_limit_reset_time = time.time() + 120  # 2 minute cooldown
        elif code == 4014:  # Disallowed intents
            logger.error("Code 4014: Disallowed intents - check bot permissions")
            return  # Don't attempt reconnection
        
        # Calculate exponential backoff delay
        delay = min(self.base_delay * (2 ** (self.reconnect_attempts - 1)), self.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = delay * 0.1 * (0.5 - asyncio.get_event_loop().time() % 1)
        final_delay = delay + jitter
        
        # Respect rate limit reset time
        if self.rate_limit_reset_time > time.time():
            additional_delay = self.rate_limit_reset_time - time.time()
            final_delay = max(final_delay, additional_delay)
        
        logger.info(f"Waiting {final_delay:.2f} seconds before reconnection attempt")
        await asyncio.sleep(final_delay)
        
        # Reset attempts on successful long-term connection
        if time.time() - self.last_disconnect_time > 300:  # 5 minutes
            self.reconnect_attempts = 0
    
    async def _handle_normal_closure(self) -> None:
        """Handle code 1000 normal closure with enhanced logic"""
        # Code 1000 can indicate:
        # 1. Discord-requested reconnection (opcode 7)
        # 2. Server maintenance
        # 3. Network issues
        # 4. Rate limiting from HTTP requests on same event loop
        
        # Check if we're making too many HTTP requests
        current_time = time.time()
        if hasattr(self.bot, '_last_http_request_time'):
            time_since_last_request = current_time - self.bot._last_http_request_time
            if time_since_last_request < 1.0:  # Less than 1 second
                logger.warning("Frequent HTTP requests detected - may be causing WebSocket issues")
                await asyncio.sleep(2.0)  # Additional delay
    
    def on_ready(self) -> None:
        """Reset connection state on successful connection"""
        logger.info("Discord connection established successfully")
        self.reconnect_attempts = 0
        self.heartbeat_failures = 0
        self.rate_limit_reset_time = 0
    
    def on_resume(self) -> None:
        """Handle successful session resume"""
        logger.info("Discord session resumed successfully")
        self.reconnect_attempts = 0
    
    async def safe_status_change(self, activity: discord.Activity) -> bool:
        """Safely change bot status with rate limiting"""
        current_time = time.time()
        
        if current_time - self.last_status_change < self.status_change_cooldown:
            remaining_cooldown = self.status_change_cooldown - (current_time - self.last_status_change)
            logger.debug(f"Status change on cooldown for {remaining_cooldown:.1f} seconds")
            return False
        
        try:
            await self.bot.change_presence(activity=activity)
            self.last_status_change = current_time
            return True
        except Exception as e:
            logger.error(f"Failed to change status: {e}")
            return False
    
    def track_http_request(self) -> None:
        """Track HTTP requests to detect potential interference with WebSocket"""
        self.bot._last_http_request_time = time.time()


def setup_connection_handler(bot: commands.Bot) -> DiscordConnectionHandler:
    """Setup enhanced connection handling for a Discord bot"""
    handler = DiscordConnectionHandler(bot)
    
    # Override default connection error handling
    original_on_error = getattr(bot, 'on_error', None)
    
    async def enhanced_on_error(event, *args, **kwargs):
        """Enhanced error handling with connection awareness"""
        if event == 'on_connect':
            handler.on_ready()
        elif event == 'on_resumed':
            handler.on_resume()
        
        # Call original error handler if it exists
        if original_on_error:
            await original_on_error(event, *args, **kwargs)
    
    bot.on_error = enhanced_on_error
    
    # Add HTTP request tracking
    original_http_request = getattr(bot.http, 'request', None)
    if original_http_request:
        async def tracked_request(*args, **kwargs):
            handler.track_http_request()
            return await original_http_request(*args, **kwargs)
        bot.http.request = tracked_request
    
    logger.info("Enhanced Discord connection handler initialized")
    return handler