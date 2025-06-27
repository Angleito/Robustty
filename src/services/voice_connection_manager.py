"""
Enhanced Voice Connection Manager for Discord Music Bot

Handles Discord voice connections with robust error handling, retry logic,
and specific handling for WebSocket code 4006 errors (session invalidation).
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Union, List
from enum import Enum

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class VoiceConnectionState(Enum):
    """Voice connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class VoiceConnectionManager:
    """Enhanced voice connection manager with retry logic and error handling"""
    
    def __init__(self, bot):
        self.bot = bot
        self.connection_states: Dict[int, VoiceConnectionState] = {}  # guild_id -> state
        self.connection_attempts: Dict[int, int] = {}  # guild_id -> attempt count
        self.last_connection_error: Dict[int, str] = {}  # guild_id -> error message
        self.connection_locks: Dict[int, asyncio.Lock] = {}  # guild_id -> lock
        
        # Configuration
        self.max_retry_attempts = 5
        self.base_retry_delay = 2.0  # seconds
        self.max_retry_delay = 60.0  # seconds
        self.connection_timeout = 30.0  # seconds
        
        # WebSocket error codes and their meanings
        self.websocket_error_codes = {
            4006: "Session no longer valid - authentication expired",
            4009: "Session timeout - connection was idle too long",
            4011: "Server not found - voice server unavailable",
            4012: "Unknown protocol - voice protocol mismatch",
            4013: "Disconnected - forcibly removed from voice channel",
            4014: "Voice server crashed - temporary server issue",
            4015: "Unknown encryption mode - voice encryption issue"
        }

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create a lock for the guild"""
        if guild_id not in self.connection_locks:
            self.connection_locks[guild_id] = asyncio.Lock()
        return self.connection_locks[guild_id]

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        delay = self.base_retry_delay * (2 ** (attempt - 1))
        return min(delay, self.max_retry_delay)

    def _reset_connection_state(self, guild_id: int):
        """Reset connection state for a guild"""
        self.connection_states[guild_id] = VoiceConnectionState.DISCONNECTED
        self.connection_attempts[guild_id] = 0
        self.last_connection_error.pop(guild_id, None)

    async def _validate_voice_permissions(self, voice_channel: discord.VoiceChannel) -> tuple[bool, str]:
        """Validate bot permissions for voice channel"""
        if not voice_channel.guild.me:
            return False, "Bot member not found in guild"
        
        permissions = voice_channel.permissions_for(voice_channel.guild.me)
        
        missing_permissions = []
        if not permissions.connect:
            missing_permissions.append("Connect")
        if not permissions.speak:
            missing_permissions.append("Speak")
        if not permissions.use_voice_activation:
            missing_permissions.append("Use Voice Activity")
        
        if missing_permissions:
            return False, f"Missing permissions: {', '.join(missing_permissions)}"
        
        # Check if channel is full
        if voice_channel.user_limit > 0 and len(voice_channel.members) >= voice_channel.user_limit:
            return False, "Voice channel is full"
        
        return True, "Permissions validated"

    async def _handle_voice_connection_error(self, guild_id: int, error: Exception) -> bool:
        """Handle voice connection errors and determine if retry is appropriate"""
        error_str = str(error)
        logger.error(f"Voice connection error for guild {guild_id}: {error}")
        
        # Store the error
        self.last_connection_error[guild_id] = error_str
        
        # Check for specific error types
        if isinstance(error, discord.ConnectionClosed):
            code = getattr(error, 'code', None)
            if code in self.websocket_error_codes:
                description = self.websocket_error_codes[code]
                logger.error(f"WebSocket error {code} for guild {guild_id}: {description}")
                
                # Determine if we should retry based on error code
                if code in [4006, 4009, 4014]:  # Session issues and server crashes - retry
                    logger.info(f"Error {code} is retryable, will attempt reconnection")
                    return True
                elif code in [4011, 4012, 4013, 4015]:  # Server/protocol issues - less likely to succeed
                    logger.warning(f"Error {code} may not be retryable, but will try once more")
                    return self.connection_attempts.get(guild_id, 0) < 2
                else:
                    logger.error(f"Error {code} is not retryable")
                    return False
            else:
                logger.error(f"Unknown WebSocket error code: {code}")
                return True  # Try to reconnect for unknown codes
        
        elif isinstance(error, discord.ClientException):
            if "already connected" in error_str.lower():
                logger.info("Already connected error - cleaning up and retrying")
                return True
            elif "timeout" in error_str.lower():
                logger.warning("Connection timeout - will retry")
                return True
            else:
                logger.error(f"Client exception: {error_str}")
                return True  # Most client exceptions are retryable
        
        elif isinstance(error, asyncio.TimeoutError):
            logger.warning("Connection timeout - will retry")
            return True
        
        else:
            logger.error(f"Unexpected error type {type(error)}: {error_str}")
            return True  # Try to handle unknown errors

    async def _cleanup_existing_connection(self, guild_id: int, voice_client: Optional[discord.VoiceClient]):
        """Clean up existing voice connection"""
        try:
            if voice_client and voice_client.is_connected():
                logger.info(f"Cleaning up existing connection for guild {guild_id}")
                await voice_client.disconnect(force=True)
                await asyncio.sleep(1)  # Give time for cleanup
        except Exception as e:
            logger.warning(f"Error during connection cleanup for guild {guild_id}: {e}")

    async def connect_to_voice(self, voice_channel: discord.VoiceChannel, 
                             current_voice_client: Optional[discord.VoiceClient] = None) -> tuple[Optional[discord.VoiceClient], str]:
        """
        Connect to voice channel with retry logic and error handling
        
        Returns:
            Tuple of (VoiceClient or None, status_message)
        """
        guild_id = voice_channel.guild.id
        
        # Use lock to prevent concurrent connection attempts
        async with self._get_lock(guild_id):
            # Validate permissions first
            has_permissions, permission_message = await self._validate_voice_permissions(voice_channel)
            if not has_permissions:
                logger.error(f"Permission validation failed for guild {guild_id}: {permission_message}")
                self.connection_states[guild_id] = VoiceConnectionState.FAILED
                return None, f"Permission Error: {permission_message}"
            
            # Initialize connection state
            if guild_id not in self.connection_attempts:
                self.connection_attempts[guild_id] = 0
            
            max_attempts = self.max_retry_attempts
            
            for attempt in range(1, max_attempts + 1):
                try:
                    self.connection_attempts[guild_id] = attempt
                    
                    if attempt == 1:
                        self.connection_states[guild_id] = VoiceConnectionState.CONNECTING
                        logger.info(f"Attempting to connect to voice channel {voice_channel.name} in guild {guild_id}")
                    else:
                        self.connection_states[guild_id] = VoiceConnectionState.RECONNECTING
                        retry_delay = self._calculate_retry_delay(attempt - 1)
                        logger.info(f"Retry attempt {attempt}/{max_attempts} for guild {guild_id} after {retry_delay}s delay")
                        await asyncio.sleep(retry_delay)
                    
                    # Clean up any existing connection
                    await self._cleanup_existing_connection(guild_id, current_voice_client)
                    
                    # Attempt connection with timeout
                    try:
                        voice_client = await asyncio.wait_for(
                            voice_channel.connect(timeout=self.connection_timeout),
                            timeout=self.connection_timeout + 5.0
                        )
                        
                        # Verify connection is actually established
                        if voice_client and voice_client.is_connected():
                            logger.info(f"Successfully connected to voice channel in guild {guild_id} on attempt {attempt}")
                            self.connection_states[guild_id] = VoiceConnectionState.CONNECTED
                            self._reset_connection_state(guild_id)
                            return voice_client, "Connected successfully"
                        else:
                            raise Exception("Connection established but client reports as not connected")
                    
                    except asyncio.TimeoutError:
                        raise Exception(f"Connection timeout after {self.connection_timeout}s")
                
                except Exception as e:
                    logger.error(f"Connection attempt {attempt}/{max_attempts} failed for guild {guild_id}: {e}")
                    
                    # Determine if we should retry
                    should_retry = await self._handle_voice_connection_error(guild_id, e)
                    
                    if attempt >= max_attempts or not should_retry:
                        logger.error(f"All connection attempts failed for guild {guild_id}")
                        self.connection_states[guild_id] = VoiceConnectionState.FAILED
                        
                        # Create detailed error message
                        error_msg = f"Connection failed after {attempt} attempts"
                        if guild_id in self.last_connection_error:
                            error_msg += f": {self.last_connection_error[guild_id]}"
                        
                        return None, error_msg
                    
                    # Continue to next attempt
                    continue
            
            # Should never reach here, but just in case
            self.connection_states[guild_id] = VoiceConnectionState.FAILED
            return None, "Connection failed for unknown reason"

    async def move_to_voice(self, voice_channel: discord.VoiceChannel, 
                          voice_client: discord.VoiceClient) -> tuple[bool, str]:
        """
        Move to a different voice channel with error handling
        
        Returns:
            Tuple of (success, status_message)
        """
        guild_id = voice_channel.guild.id
        
        # Validate permissions for new channel
        has_permissions, permission_message = await self._validate_voice_permissions(voice_channel)
        if not has_permissions:
            return False, f"Permission Error: {permission_message}"
        
        try:
            logger.info(f"Moving to voice channel {voice_channel.name} in guild {guild_id}")
            
            if hasattr(voice_client, 'move_to'):
                await voice_client.move_to(voice_channel)
                return True, f"Moved to {voice_channel.name}"
            else:
                # Fallback: disconnect and reconnect
                await voice_client.disconnect(force=True)
                new_client, message = await self.connect_to_voice(voice_channel)
                if new_client:
                    return True, f"Reconnected to {voice_channel.name}"
                else:
                    return False, f"Failed to reconnect: {message}"
        
        except Exception as e:
            logger.error(f"Error moving to voice channel in guild {guild_id}: {e}")
            return False, f"Move failed: {str(e)}"

    async def disconnect_from_voice(self, guild_id: int, voice_client: Optional[discord.VoiceClient], 
                                  force: bool = False) -> tuple[bool, str]:
        """
        Disconnect from voice channel with cleanup
        
        Returns:
            Tuple of (success, status_message)
        """
        try:
            if voice_client and voice_client.is_connected():
                logger.info(f"Disconnecting from voice in guild {guild_id}")
                await voice_client.disconnect(force=force)
                
            self._reset_connection_state(guild_id)
            return True, "Disconnected successfully"
        
        except Exception as e:
            logger.error(f"Error disconnecting from voice in guild {guild_id}: {e}")
            # Still reset state even if disconnect failed
            self._reset_connection_state(guild_id)
            return False, f"Disconnect error: {str(e)}"

    def get_connection_state(self, guild_id: int) -> VoiceConnectionState:
        """Get current connection state for a guild"""
        return self.connection_states.get(guild_id, VoiceConnectionState.DISCONNECTED)

    def get_connection_info(self, guild_id: int) -> Dict:
        """Get detailed connection information for a guild"""
        return {
            'state': self.get_connection_state(guild_id).value,
            'attempts': self.connection_attempts.get(guild_id, 0),
            'last_error': self.last_connection_error.get(guild_id),
            'max_attempts': self.max_retry_attempts
        }

    def get_health_status(self) -> Dict:
        """Get overall health status of voice connections"""
        total_guilds = len(self.connection_states)
        connected_count = sum(1 for state in self.connection_states.values() 
                            if state == VoiceConnectionState.CONNECTED)
        failed_count = sum(1 for state in self.connection_states.values() 
                         if state == VoiceConnectionState.FAILED)
        
        return {
            'total_guilds': total_guilds,
            'connected': connected_count,
            'failed': failed_count,
            'connection_rate': connected_count / total_guilds if total_guilds > 0 else 0,
            'states': {guild_id: state.value for guild_id, state in self.connection_states.items()}
        }

    async def health_check_connections(self) -> List[int]:
        """
        Check health of all active connections and return list of unhealthy guild IDs
        """
        unhealthy_guilds = []
        
        for guild_id, state in self.connection_states.items():
            if state == VoiceConnectionState.CONNECTED:
                # Check if the voice client is actually still connected
                guild = self.bot.get_guild(guild_id)
                if guild and guild.voice_client:
                    if not guild.voice_client.is_connected():
                        logger.warning(f"Voice client for guild {guild_id} reports as disconnected")
                        self.connection_states[guild_id] = VoiceConnectionState.DISCONNECTED
                        unhealthy_guilds.append(guild_id)
                else:
                    logger.warning(f"No voice client found for guild {guild_id} marked as connected")
                    self.connection_states[guild_id] = VoiceConnectionState.DISCONNECTED
                    unhealthy_guilds.append(guild_id)
        
        return unhealthy_guilds