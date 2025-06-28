"""
Enhanced Voice Connection Manager for Discord Music Bot

Handles Discord voice connections with robust error handling, retry logic,
and specific handling for WebSocket code 4006 errors (session invalidation).

VPS-Specific Optimizations:
- Detects containerized/VPS environments
- Uses longer retry delays for VPS deployments
- Implements session recreation for 4006 errors
- Adds network stability checks
- Includes circuit breaker pattern for voice connections
"""

import asyncio
import logging
import time
import os
import socket
from typing import Dict, Optional, Union, List, Tuple
from enum import Enum
from datetime import datetime, timedelta

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
    SESSION_INVALID = "session_invalid"
    CIRCUIT_OPEN = "circuit_open"


class DeploymentEnvironment(Enum):
    """Deployment environment types"""
    LOCAL = "local"
    DOCKER = "docker"
    VPS = "vps"


class VoiceConnectionManager:
    """Enhanced voice connection manager with VPS-specific optimizations"""
    
    def __init__(self, bot):
        self.bot = bot
        self.connection_states: Dict[int, VoiceConnectionState] = {}  # guild_id -> state
        self.connection_attempts: Dict[int, int] = {}  # guild_id -> attempt count
        self.last_connection_error: Dict[int, str] = {}  # guild_id -> error message
        self.connection_locks: Dict[int, asyncio.Lock] = {}  # guild_id -> lock
        self.session_states: Dict[int, Dict] = {}  # guild_id -> session info
        self.connection_failures: Dict[int, List[datetime]] = {}  # guild_id -> failure timestamps
        self.last_successful_connection: Dict[int, datetime] = {}  # guild_id -> last success time
        
        # Detect deployment environment
        self.environment = self._detect_environment()
        logger.info(f"Voice Connection Manager initialized in {self.environment.value} environment")
        
        # Configuration based on environment
        if self.environment == DeploymentEnvironment.VPS:
            # VPS-specific configuration with longer delays and session recreation
            self.max_retry_attempts = 3  # Reduced for faster recovery
            self.base_retry_delay = 8.0  # Discord requires 6+ seconds, use 8 for VPS
            self.max_retry_delay = 30.0  # Faster max delay
            self.connection_timeout = 60.0  # Longer timeout for VPS
            self.session_timeout = 180.0  # 3 minutes (shorter for faster refresh)
            self.circuit_breaker_threshold = 3  # Faster circuit breaking
            self.circuit_breaker_timeout = 120.0  # 2 minutes
            self.network_check_interval = 10.0  # seconds
            self.force_session_recreation = True  # Always recreate sessions on VPS
        else:
            # Local/Docker configuration
            self.max_retry_attempts = 5
            self.base_retry_delay = 2.0  # seconds
            self.max_retry_delay = 60.0  # seconds
            self.connection_timeout = 30.0  # seconds
            self.session_timeout = 180.0  # 3 minutes
            self.circuit_breaker_threshold = 3
            self.circuit_breaker_timeout = 180.0  # 3 minutes
            self.network_check_interval = 5.0  # seconds
            self.force_session_recreation = False  # Normal session handling
        
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
        
        # Session-specific error codes that require new session
        self.session_error_codes = {4006, 4009}
        
        # Initialize health monitoring
        self._start_health_monitoring()

    def _detect_environment(self) -> DeploymentEnvironment:
        """Detect deployment environment (Local, Docker, VPS)"""
        # Check for Docker environment
        if os.path.exists('/.dockerenv'):
            # Running in Docker container
            # Check if it's on VPS by looking for specific indicators
            if self._is_vps_environment():
                return DeploymentEnvironment.VPS
            return DeploymentEnvironment.DOCKER
        
        # Check for VPS indicators
        if self._is_vps_environment():
            return DeploymentEnvironment.VPS
        
        # Default to local
        return DeploymentEnvironment.LOCAL
    
    def _is_vps_environment(self) -> bool:
        """Check if running on VPS by various indicators"""
        vps_indicators = [
            # Environment variables
            os.getenv('IS_VPS', '').lower() == 'true',
            os.getenv('DEPLOYMENT_TYPE', '').lower() == 'vps',
            os.getenv('REDIS_URL', '').startswith('redis://redis:'),  # Container networking
            
            # Check hostname patterns common on VPS
            'vps' in socket.gethostname().lower(),
            'server' in socket.gethostname().lower(),
            
            # Check for headless environment
            os.getenv('DISPLAY') is None and os.name == 'posix',
        ]
        
        return any(vps_indicators)

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create a lock for the guild"""
        if guild_id not in self.connection_locks:
            self.connection_locks[guild_id] = asyncio.Lock()
        return self.connection_locks[guild_id]

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter"""
        base_delay = self.base_retry_delay * (2 ** (attempt - 1))
        delay = min(base_delay, self.max_retry_delay)
        
        # Add jitter for VPS to avoid thundering herd
        if self.environment == DeploymentEnvironment.VPS:
            import random
            jitter = random.uniform(0, delay * 0.1)  # Up to 10% jitter
            delay += jitter
        
        return delay

    def _reset_connection_state(self, guild_id: int):
        """Reset connection state for a guild"""
        self.connection_states[guild_id] = VoiceConnectionState.DISCONNECTED
        self.connection_attempts[guild_id] = 0
        self.last_connection_error.pop(guild_id, None)
        self.session_states.pop(guild_id, None)

    def _is_circuit_open(self, guild_id: int) -> bool:
        """Check if circuit breaker is open for a guild"""
        if guild_id not in self.connection_failures:
            return False
        
        # Get recent failures
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.circuit_breaker_timeout)
        recent_failures = [
            ts for ts in self.connection_failures[guild_id]
            if ts > cutoff
        ]
        
        # Update the list
        self.connection_failures[guild_id] = recent_failures
        
        # Check if circuit should be open
        if len(recent_failures) >= self.circuit_breaker_threshold:
            # Check if we should try to close the circuit
            if recent_failures[-1] < now - timedelta(seconds=60):  # Try after 1 minute
                logger.info(f"Circuit breaker for guild {guild_id}: attempting to close")
                return False
            return True
        
        return False

    def _record_failure(self, guild_id: int):
        """Record a connection failure for circuit breaker"""
        if guild_id not in self.connection_failures:
            self.connection_failures[guild_id] = []
        self.connection_failures[guild_id].append(datetime.now())

    def _record_success(self, guild_id: int):
        """Record a successful connection"""
        self.last_successful_connection[guild_id] = datetime.now()
        # Clear failure history on success
        self.connection_failures.pop(guild_id, None)

    async def _check_network_stability(self) -> bool:
        """Check network stability before attempting voice connection"""
        if self.environment != DeploymentEnvironment.VPS:
            return True  # Skip for non-VPS environments
        
        try:
            # Check Discord API endpoint
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://discord.com/api/v10/gateway',
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning(f"Network stability check failed: {e}")
            return False

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

    async def _create_new_session(self, guild_id: int):
        """Create a new voice session for a guild"""
        self.session_states[guild_id] = {
            'created_at': datetime.now(),
            'session_id': f"{guild_id}_{int(time.time())}",
            'reconnect_count': 0
        }
        logger.info(f"Created new voice session for guild {guild_id}: {self.session_states[guild_id]['session_id']}")

    def _is_session_valid(self, guild_id: int) -> bool:
        """Check if current session is still valid"""
        if guild_id not in self.session_states:
            return False
        
        session = self.session_states[guild_id]
        age = (datetime.now() - session['created_at']).total_seconds()
        
        return age < self.session_timeout

    async def _handle_voice_connection_error(self, guild_id: int, error: Exception) -> Tuple[bool, bool]:
        """
        Handle voice connection errors and determine if retry is appropriate
        
        Returns:
            Tuple of (should_retry, needs_new_session)
        """
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
                
                # Session errors require new session
                if code in self.session_error_codes or (self.environment == DeploymentEnvironment.VPS and self.force_session_recreation):
                    logger.info(f"Error {code} requires new session for guild {guild_id} (VPS mode: {self.environment == DeploymentEnvironment.VPS})")
                    self.connection_states[guild_id] = VoiceConnectionState.SESSION_INVALID
                    # Force disconnect and cleanup on VPS
                    if self.environment == DeploymentEnvironment.VPS:
                        await self._force_disconnect_guild(guild_id)
                    return True, True
                
                # Determine if we should retry based on error code
                if code in [4014]:  # Server crashes - retry
                    logger.info(f"Error {code} is retryable, will attempt reconnection")
                    return True, False
                elif code in [4011, 4012, 4013, 4015]:  # Server/protocol issues
                    if self.environment == DeploymentEnvironment.VPS:
                        # More aggressive retry on VPS
                        return self.connection_attempts.get(guild_id, 0) < 4, False
                    else:
                        return self.connection_attempts.get(guild_id, 0) < 2, False
                else:
                    logger.error(f"Error {code} is not retryable")
                    return False, False
            else:
                logger.error(f"Unknown WebSocket error code: {code}")
                return True, False  # Try to reconnect for unknown codes
        
        elif isinstance(error, discord.ClientException):
            if "already connected" in error_str.lower():
                logger.info("Already connected error - cleaning up and retrying")
                return True, True  # New session to clean up state
            elif "timeout" in error_str.lower():
                logger.warning("Connection timeout - will retry")
                return True, False
            else:
                logger.error(f"Client exception: {error_str}")
                return True, False  # Most client exceptions are retryable
        
        elif isinstance(error, asyncio.TimeoutError):
            logger.warning("Connection timeout - will retry")
            # VPS environments may need new session on timeout
            return True, self.environment == DeploymentEnvironment.VPS
        
        else:
            logger.error(f"Unexpected error type {type(error)}: {error_str}")
            return True, False  # Try to handle unknown errors

    async def _cleanup_existing_connection(self, guild_id: int, voice_client: Optional[discord.VoiceClient]):
        """Clean up existing voice connection with session cleanup"""
        try:
            if voice_client and voice_client.is_connected():
                logger.info(f"Cleaning up existing connection for guild {guild_id}")
                await voice_client.disconnect(force=True)
                await asyncio.sleep(2 if self.environment == DeploymentEnvironment.VPS else 1)
        except Exception as e:
            logger.warning(f"Error during connection cleanup for guild {guild_id}: {e}")
        
        # Clear session state
        self.session_states.pop(guild_id, None)

    async def connect_to_voice(self, voice_channel: discord.VoiceChannel, 
                             current_voice_client: Optional[discord.VoiceClient] = None) -> tuple[Optional[discord.VoiceClient], str]:
        """
        Connect to voice channel with retry logic and error handling
        
        Returns:
            Tuple of (VoiceClient or None, status_message)
        """
        guild_id = voice_channel.guild.id
        
        # Check circuit breaker
        if self._is_circuit_open(guild_id):
            logger.warning(f"Circuit breaker open for guild {guild_id}")
            self.connection_states[guild_id] = VoiceConnectionState.CIRCUIT_OPEN
            return None, "Voice connection temporarily disabled due to repeated failures. Please try again in a few minutes."
        
        # Use lock to prevent concurrent connection attempts
        async with self._get_lock(guild_id):
            # Check network stability for VPS
            if self.environment == DeploymentEnvironment.VPS:
                if not await self._check_network_stability():
                    return None, "Network connectivity issues detected. Please check bot's internet connection."
            
            # Validate permissions first
            has_permissions, permission_message = await self._validate_voice_permissions(voice_channel)
            if not has_permissions:
                logger.error(f"Permission validation failed for guild {guild_id}: {permission_message}")
                self.connection_states[guild_id] = VoiceConnectionState.FAILED
                return None, f"Permission Error: {permission_message}"
            
            # Initialize connection state
            if guild_id not in self.connection_attempts:
                self.connection_attempts[guild_id] = 0
            
            # Create new session if needed
            if not self._is_session_valid(guild_id):
                await self._create_new_session(guild_id)
            
            max_attempts = self.max_retry_attempts
            needs_new_session = False
            
            for attempt in range(1, max_attempts + 1):
                try:
                    self.connection_attempts[guild_id] = attempt
                    
                    if attempt == 1:
                        self.connection_states[guild_id] = VoiceConnectionState.CONNECTING
                        logger.info(f"Attempting to connect to voice channel {voice_channel.name} in guild {guild_id} (Environment: {self.environment.value})")
                    else:
                        self.connection_states[guild_id] = VoiceConnectionState.RECONNECTING
                        retry_delay = self._calculate_retry_delay(attempt - 1)
                        logger.info(f"Retry attempt {attempt}/{max_attempts} for guild {guild_id} after {retry_delay:.1f}s delay")
                        await asyncio.sleep(retry_delay)
                    
                    # Handle session recreation if needed
                    if needs_new_session:
                        logger.info(f"Creating new session for guild {guild_id} before connection attempt")
                        await self._cleanup_existing_connection(guild_id, current_voice_client)
                        await self._create_new_session(guild_id)
                        current_voice_client = None
                        needs_new_session = False
                    else:
                        # Normal cleanup
                        await self._cleanup_existing_connection(guild_id, current_voice_client)
                    
                    # Attempt connection with timeout
                    try:
                        voice_client = await asyncio.wait_for(
                            voice_channel.connect(
                                timeout=self.connection_timeout,
                                reconnect=True,  # Enable auto-reconnect
                                cls=discord.VoiceClient
                            ),
                            timeout=self.connection_timeout + 5.0
                        )
                        
                        # Verify connection is actually established
                        if voice_client and voice_client.is_connected():
                            logger.info(f"Successfully connected to voice channel in guild {guild_id} on attempt {attempt}")
                            self.connection_states[guild_id] = VoiceConnectionState.CONNECTED
                            self._record_success(guild_id)
                            self._reset_connection_state(guild_id)
                            return voice_client, "Connected successfully"
                        else:
                            raise Exception("Connection established but client reports as not connected")
                    
                    except asyncio.TimeoutError:
                        raise Exception(f"Connection timeout after {self.connection_timeout}s")
                
                except Exception as e:
                    logger.error(f"Connection attempt {attempt}/{max_attempts} failed for guild {guild_id}: {e}")
                    
                    # Determine if we should retry and if we need a new session
                    should_retry, needs_new_session = await self._handle_voice_connection_error(guild_id, e)
                    
                    # Record failure for circuit breaker
                    self._record_failure(guild_id)
                    
                    if attempt >= max_attempts or not should_retry:
                        logger.error(f"All connection attempts failed for guild {guild_id}")
                        self.connection_states[guild_id] = VoiceConnectionState.FAILED
                        
                        # Create detailed error message
                        error_msg = f"Connection failed after {attempt} attempts"
                        if guild_id in self.last_connection_error:
                            error_msg += f": {self.last_connection_error[guild_id]}"
                        
                        if self.environment == DeploymentEnvironment.VPS:
                            error_msg += "\n\nNote: Running on VPS - voice connections may be less stable due to network conditions."
                        
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
        info = {
            'state': self.get_connection_state(guild_id).value,
            'attempts': self.connection_attempts.get(guild_id, 0),
            'last_error': self.last_connection_error.get(guild_id),
            'max_attempts': self.max_retry_attempts,
            'environment': self.environment.value,
        }
        
        # Add session info if available
        if guild_id in self.session_states:
            session = self.session_states[guild_id]
            info['session'] = {
                'id': session['session_id'],
                'age_seconds': (datetime.now() - session['created_at']).total_seconds(),
                'reconnect_count': session['reconnect_count']
            }
        
        # Add circuit breaker info
        if guild_id in self.connection_failures:
            recent_failures = len([
                ts for ts in self.connection_failures[guild_id]
                if ts > datetime.now() - timedelta(seconds=self.circuit_breaker_timeout)
            ])
            info['circuit_breaker'] = {
                'failures': recent_failures,
                'threshold': self.circuit_breaker_threshold,
                'is_open': self._is_circuit_open(guild_id)
            }
        
        # Add last successful connection
        if guild_id in self.last_successful_connection:
            info['last_success'] = {
                'timestamp': self.last_successful_connection[guild_id].isoformat(),
                'age_seconds': (datetime.now() - self.last_successful_connection[guild_id]).total_seconds()
            }
        
        return info

    def get_health_status(self) -> Dict:
        """Get overall health status of voice connections"""
        total_guilds = len(self.connection_states)
        connected_count = sum(1 for state in self.connection_states.values() 
                            if state == VoiceConnectionState.CONNECTED)
        failed_count = sum(1 for state in self.connection_states.values() 
                         if state == VoiceConnectionState.FAILED)
        circuit_open_count = sum(1 for guild_id in self.connection_states 
                               if self._is_circuit_open(guild_id))
        
        return {
            'environment': self.environment.value,
            'total_guilds': total_guilds,
            'connected': connected_count,
            'failed': failed_count,
            'circuit_breakers_open': circuit_open_count,
            'connection_rate': connected_count / total_guilds if total_guilds > 0 else 0,
            'states': {guild_id: state.value for guild_id, state in self.connection_states.items()},
            'configuration': {
                'max_retry_attempts': self.max_retry_attempts,
                'base_retry_delay': self.base_retry_delay,
                'connection_timeout': self.connection_timeout,
                'circuit_breaker_threshold': self.circuit_breaker_threshold
            }
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

    async def _force_disconnect_guild(self, guild_id: int):
        """Force disconnect from voice channel with cleanup (VPS-specific)"""
        try:
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                logger.info(f"Force disconnecting from voice channel in guild {guild_id}")
                await guild.voice_client.disconnect(force=True)
                await asyncio.sleep(2)  # Give time for cleanup
            
            # Clean up session state
            if guild_id in self.session_states:
                del self.session_states[guild_id]
                logger.info(f"Cleaned up session state for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error during force disconnect for guild {guild_id}: {e}")

    def _start_health_monitoring(self):
        """Start background health monitoring task"""
        async def monitor_health():
            """Background task to monitor voice connection health"""
            while True:
                try:
                    await asyncio.sleep(60)  # Check every minute
                    unhealthy = await self.health_check_connections()
                    if unhealthy:
                        logger.info(f"Health check found {len(unhealthy)} unhealthy connections")
                except Exception as e:
                    logger.error(f"Error in voice connection health monitoring: {e}")
        
        # Start the monitoring task
        asyncio.create_task(monitor_health())