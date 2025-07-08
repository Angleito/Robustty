"""HTTP Session Manager for managing aiohttp sessions."""

import asyncio
import logging
from typing import Optional
import aiohttp
from aiohttp import ClientTimeout

from ..utils.network_routing import get_http_client

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """Manages HTTP sessions for the application with network routing support."""
    
    def __init__(self):
        self._sessions: dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()
        
    async def get_session(self, name: str = "default", **kwargs) -> aiohttp.ClientSession:
        """Get or create an HTTP session with network routing support."""
        async with self._lock:
            if name not in self._sessions or self._sessions[name].closed:
                # Use network routing for better session management
                http_client = get_http_client()
                await http_client.initialize()
                
                # Create a generic session using network routing
                from ..utils.network_routing import ServiceType
                interface = http_client.router.get_interface_for_service(ServiceType.GENERIC)
                
                # Create session with network-aware configuration
                timeout = kwargs.get('timeout', ClientTimeout(total=30, connect=10, sock_read=10))
                
                connector_kwargs = {
                    'limit': 100,
                    'limit_per_host': 30,
                    'ttl_dns_cache': 300
                }
                
                # Configure interface binding if available
                if interface and interface.ip_address != "0.0.0.0":
                    try:
                        connector_kwargs['local_addr'] = (interface.ip_address, 0)
                        logger.debug(f"Binding session {name} to interface {interface.name}")
                    except Exception as e:
                        logger.warning(f"Failed to bind session {name} to interface: {e}")
                
                connector = aiohttp.TCPConnector(**connector_kwargs)
                session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                    **{k: v for k, v in kwargs.items() if k != 'timeout'}
                )
                
                self._sessions[name] = session
                logger.debug(f"Created new HTTP session: {name}")
                
            return self._sessions[name]
    
    async def close(self):
        """Close all HTTP sessions."""
        async with self._lock:
            for name, session in self._sessions.items():
                if not session.closed:
                    await session.close()
                    logger.debug(f"Closed HTTP session: {name}")
            self._sessions.clear()


# Global session manager instance
_session_manager = HTTPSessionManager()


async def get_session_manager() -> HTTPSessionManager:
    """Get the global session manager instance."""
    return _session_manager


async def get_session() -> aiohttp.ClientSession:
    """Get the global HTTP session."""
    return await _session_manager.get_session()


async def close_session():
    """Close the global HTTP session."""
    await _session_manager.close()


async def cleanup_session_manager():
    """Cleanup the session manager (alias for close_session)."""
    await close_session()