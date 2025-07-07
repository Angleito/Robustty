"""HTTP Session Manager for managing aiohttp sessions."""

import asyncio
import logging
from typing import Optional
import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """Manages HTTP sessions for the application."""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an HTTP session."""
        async with self._lock:
            if self._session is None or self._session.closed:
                timeout = ClientTimeout(total=30, connect=10, sock_read=10)
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300
                )
                self._session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector
                )
                logger.debug("Created new HTTP session")
            return self._session
    
    async def close(self):
        """Close the HTTP session."""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                logger.debug("Closed HTTP session")
                self._session = None


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