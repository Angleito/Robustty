"""
Network connectivity utilities for Discord gateway and external service connections.

This module provides pre-flight network checks, DNS fallback logic, and
Discord gateway region fallback mechanisms for robust network connectivity.
"""

import asyncio
import logging
import random
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

import aiohttp
import discord
import dns.asyncresolver
import dns.exception

logger = logging.getLogger(__name__)


class ConnectivityStatus(Enum):
    """Network connectivity status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class NetworkEndpoint:
    """Network endpoint configuration"""

    name: str
    url: str
    timeout: int = 5
    required: bool = True
    priority: int = 1  # Lower number = higher priority


@dataclass
class DNSServer:
    """DNS server configuration"""

    address: str
    name: str
    timeout: int = 3
    priority: int = 1  # Lower number = higher priority


@dataclass
class DiscordGateway:
    """Discord gateway configuration"""

    region: str
    endpoint: str
    priority: int = 1  # Lower number = higher priority


@dataclass
class ConnectivityCheckResult:
    """Result of connectivity check"""

    status: ConnectivityStatus
    successful_checks: int
    failed_checks: int
    total_checks: int
    response_times: Dict[str, float]
    errors: List[str]
    recommended_actions: List[str]

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100


class NetworkConnectivityChecker:
    """Network connectivity checker with fallback mechanisms"""

    # Default DNS servers with priorities - prioritize reliable public DNS
    DEFAULT_DNS_SERVERS = [
        # Primary tier - fastest and most reliable
        DNSServer("1.1.1.1", "Cloudflare Primary", timeout=3, priority=1),
        DNSServer("8.8.8.8", "Google Primary", timeout=3, priority=2),
        DNSServer("9.9.9.9", "Quad9 Primary", timeout=3, priority=3),
        # Secondary tier - backup for primary services
        DNSServer("1.0.0.1", "Cloudflare Secondary", timeout=4, priority=4),
        DNSServer("8.8.4.4", "Google Secondary", timeout=4, priority=5),
        DNSServer("149.112.112.112", "Quad9 Secondary", timeout=4, priority=6),
        # Tertiary tier - additional fallbacks
        DNSServer("208.67.222.222", "OpenDNS Primary", timeout=5, priority=7),
        DNSServer("208.67.220.220", "OpenDNS Secondary", timeout=5, priority=8),
    ]

    # Default Discord gateways with priorities - prioritize main gateway with regional fallbacks
    DEFAULT_DISCORD_GATEWAYS = [
        # Primary Discord gateway (most reliable)
        DiscordGateway("global", "gateway.discord.gg", priority=1),
        # Regional fallbacks - main regions
        DiscordGateway("us-east", "gateway-us-east-1.discord.gg", priority=2),
        DiscordGateway("us-west", "gateway-us-west-1.discord.gg", priority=3),
        DiscordGateway("us-central", "gateway-us-central-1.discord.gg", priority=4),
        # International fallbacks
        DiscordGateway("europe", "gateway-europe-1.discord.gg", priority=5),
        DiscordGateway("asia", "gateway-asia-1.discord.gg", priority=6),
        DiscordGateway("sydney", "gateway-sydney-1.discord.gg", priority=7),
        # Additional fallback using generic gateway
        DiscordGateway("fallback", "gateway.discord.gg", priority=8),
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.dns_servers = self._load_dns_servers()
        self.discord_gateways = self._load_discord_gateways()
        self.essential_endpoints = self._load_essential_endpoints()
        self.current_dns_server: Optional[DNSServer] = None
        self.current_gateway: Optional[DiscordGateway] = None

    def _load_dns_servers(self) -> List[DNSServer]:
        """Load DNS servers from config or use defaults"""
        dns_config = self.config.get("network", {}).get("dns_servers", [])

        if not dns_config:
            return self.DEFAULT_DNS_SERVERS.copy()

        servers = []
        for i, server_config in enumerate(dns_config):
            servers.append(
                DNSServer(
                    address=server_config["address"],
                    name=server_config.get("name", f"DNS-{i+1}"),
                    timeout=server_config.get("timeout", 3),
                    priority=i + 1,
                )
            )

        # Add defaults as fallback
        servers.extend(self.DEFAULT_DNS_SERVERS)
        return sorted(servers, key=lambda x: x.priority)

    def _load_discord_gateways(self) -> List[DiscordGateway]:
        """Load Discord gateways from config or use defaults"""
        gateway_config = self.config.get("network", {}).get("discord_gateways", [])

        if not gateway_config:
            return self.DEFAULT_DISCORD_GATEWAYS.copy()

        gateways = []
        for i, gw_config in enumerate(gateway_config):
            gateways.append(
                DiscordGateway(
                    region=gw_config["region"],
                    endpoint=gw_config["endpoint"],
                    priority=gw_config.get("priority", i + 1),
                )
            )

        # Add defaults as fallback
        gateways.extend(self.DEFAULT_DISCORD_GATEWAYS)
        return sorted(gateways, key=lambda x: x.priority)

    def _load_essential_endpoints(self) -> List[NetworkEndpoint]:
        """Load essential endpoints to check"""
        default_endpoints = [
            NetworkEndpoint(
                "Discord API",
                "https://discord.com/api/v10/gateway",
                timeout=10,
                required=True,
                priority=1,
            ),
            NetworkEndpoint(
                "Discord CDN",
                "https://cdn.discordapp.com",
                timeout=5,
                required=True,
                priority=2,
            ),
            NetworkEndpoint(
                "Google DNS Check",
                "https://dns.google",
                timeout=5,
                required=False,
                priority=3,
            ),
            NetworkEndpoint(
                "Cloudflare Check",
                "https://1.1.1.1",
                timeout=5,
                required=False,
                priority=4,
            ),
        ]

        # Add platform endpoints from config
        endpoint_config = self.config.get("network", {}).get("essential_endpoints", [])
        for endpoint in endpoint_config:
            default_endpoints.append(
                NetworkEndpoint(
                    name=endpoint["name"],
                    url=endpoint["url"],
                    timeout=endpoint.get("timeout", 5),
                    required=endpoint.get("required", False),
                    priority=endpoint.get("priority", 10),
                )
            )

        return sorted(default_endpoints, key=lambda x: x.priority)

    async def check_dns_resolution(
        self, domain: str, dns_server: DNSServer
    ) -> Tuple[bool, float, Optional[str]]:
        """Check DNS resolution with specific DNS server with enhanced error handling"""
        start_time = time.time()

        try:
            resolver = dns.asyncresolver.Resolver()
            resolver.nameservers = [dns_server.address]
            resolver.timeout = dns_server.timeout
            resolver.lifetime = dns_server.timeout * 2  # Allow more time for lifetime
            # Configure for reliability
            resolver.use_edns = False  # Some restrictive networks block EDNS
            resolver.retry_servfail = True  # Retry on SERVFAIL
            resolver.ndots = 1  # Reduce unnecessary queries

            # Try A record first, then AAAA as fallback
            try:
                await resolver.resolve(domain, "A")
            except (dns.exception.NXDOMAIN, dns.exception.NoAnswer):
                # Try AAAA if A record fails
                await resolver.resolve(domain, "AAAA")

            response_time = time.time() - start_time
            return True, response_time, None

        except dns.exception.Timeout:
            response_time = time.time() - start_time
            return (
                False,
                response_time,
                f"DNS timeout after {dns_server.timeout}s ({dns_server.name})",
            )
        except dns.exception.NXDOMAIN:
            response_time = time.time() - start_time
            return (
                False,
                response_time,
                f"Domain '{domain}' not found ({dns_server.name})",
            )
        except dns.exception.NoNameservers:
            response_time = time.time() - start_time
            return False, response_time, f"No nameservers available ({dns_server.name})"
        except dns.exception.NoAnswer:
            response_time = time.time() - start_time
            return (
                False,
                response_time,
                f"No answer for domain '{domain}' ({dns_server.name})",
            )
        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            return (
                False,
                response_time,
                f"DNS resolution failed ({dns_server.name}): {error_type}: {str(e)}",
            )

    async def find_working_dns_server(
        self, test_domains: List[str] = None
    ) -> Optional[DNSServer]:
        """Find the first working DNS server using multiple test domains"""
        if test_domains is None:
            test_domains = ["discord.com", "google.com", "cloudflare.com"]

        for dns_server in self.dns_servers:
            dns_success = False
            best_response_time = float("inf")

            # Test multiple domains to ensure DNS server is actually working
            for test_domain in test_domains:
                success, response_time, error = await self.check_dns_resolution(
                    test_domain, dns_server
                )
                if success:
                    dns_success = True
                    best_response_time = min(best_response_time, response_time)
                    break  # Found working domain, no need to test others
                else:
                    logger.debug(
                        f"DNS server {dns_server.name} failed for {test_domain}: {error}"
                    )

            if dns_success:
                logger.info(
                    f"Using DNS server: {dns_server.name} ({dns_server.address}) - {best_response_time:.2f}s"
                )
                self.current_dns_server = dns_server
                return dns_server
            else:
                logger.warning(
                    f"DNS server {dns_server.name} failed for all test domains"
                )

        logger.error(
            "No working DNS servers found - this indicates severe network connectivity issues"
        )
        return None

    async def check_endpoint_connectivity(
        self, endpoint: NetworkEndpoint
    ) -> Tuple[bool, float, Optional[str]]:
        """Check connectivity to a specific endpoint"""
        start_time = time.time()

        try:
            timeout = aiohttp.ClientTimeout(total=endpoint.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(endpoint.url) as response:
                    response_time = time.time() - start_time
                    success = response.status < 400
                    error = None if success else f"HTTP {response.status}"
                    return success, response_time, error

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return False, response_time, f"Timeout after {endpoint.timeout}s"
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, str(e)

    async def check_discord_gateway(
        self, gateway: DiscordGateway
    ) -> Tuple[bool, float, Optional[str]]:
        """Check Discord gateway connectivity with enhanced error handling"""
        start_time = time.time()

        try:
            # First try DNS resolution for the gateway
            if self.current_dns_server:
                dns_success, _, dns_error = await self.check_dns_resolution(
                    gateway.endpoint, self.current_dns_server
                )
                if not dns_success:
                    response_time = time.time() - start_time
                    return False, response_time, f"DNS resolution failed: {dns_error}"

            # Try to connect to the WebSocket gateway
            url = f"wss://{gateway.endpoint}/?v=10&encoding=json"
            timeout = aiohttp.ClientTimeout(total=10, connect=5)

            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=aiohttp.TCPConnector(limit=1, ttl_dns_cache=30),
            ) as session:
                try:
                    async with session.ws_connect(
                        url,
                        heartbeat=30,
                        compress=0,  # Disable compression for faster connection
                    ) as ws:
                        # Wait for hello message with timeout
                        msg = await asyncio.wait_for(ws.receive(), timeout=5)
                        response_time = time.time() - start_time

                        if msg.type == aiohttp.WSMsgType.TEXT:
                            return True, response_time, None
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            return (
                                False,
                                response_time,
                                f"WebSocket error: {ws.exception()}",
                            )
                        else:
                            return (
                                False,
                                response_time,
                                f"Unexpected message type: {msg.type}",
                            )
                except aiohttp.WSServerHandshakeError as e:
                    response_time = time.time() - start_time
                    return (
                        False,
                        response_time,
                        f"WebSocket handshake failed: {e.status} {e.message}",
                    )

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            return False, response_time, f"Gateway connection timeout after 10s"
        except aiohttp.ClientConnectorError as e:
            response_time = time.time() - start_time
            return False, response_time, f"Connection error: {str(e)}"
        except OSError as e:
            response_time = time.time() - start_time
            # Handle "No address associated with hostname" and similar OS errors
            if "No address associated with hostname" in str(e):
                return (
                    False,
                    response_time,
                    f"DNS resolution failed for {gateway.endpoint}",
                )
            return False, response_time, f"Network error: {str(e)}"
        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            return False, response_time, f"{error_type}: {str(e)}"

    async def find_working_discord_gateway(self) -> Optional[DiscordGateway]:
        """Find the best working Discord gateway"""
        best_gateway = None
        best_response_time = float("inf")

        for gateway in self.discord_gateways:
            success, response_time, error = await self.check_discord_gateway(gateway)
            if success:
                logger.info(
                    f"Discord gateway {gateway.region} ({gateway.endpoint}) - {response_time:.2f}s"
                )
                if response_time < best_response_time:
                    best_response_time = response_time
                    best_gateway = gateway
            else:
                logger.warning(f"Discord gateway {gateway.region} failed: {error}")

        if best_gateway:
            logger.info(
                f"Selected Discord gateway: {best_gateway.region} ({best_response_time:.2f}s)"
            )
            self.current_gateway = best_gateway
            return best_gateway

        logger.error("No working Discord gateways found")
        return None

    async def run_full_connectivity_check(self) -> ConnectivityCheckResult:
        """Run comprehensive connectivity check"""
        logger.info("Starting comprehensive network connectivity check...")

        successful_checks = 0
        failed_checks = 0
        total_checks = 0
        response_times = {}
        errors = []
        recommended_actions = []

        # 1. Check DNS resolution
        logger.info("Checking DNS resolution...")
        working_dns = await self.find_working_dns_server()
        if working_dns:
            successful_checks += 1
            response_times["dns"] = 0.1  # Placeholder
        else:
            failed_checks += 1
            errors.append("No working DNS servers found")
            recommended_actions.append(
                "Check internet connection and DNS configuration"
            )
        total_checks += 1

        # 2. Check essential endpoints
        logger.info("Checking essential endpoints...")
        for endpoint in self.essential_endpoints:
            success, response_time, error = await self.check_endpoint_connectivity(
                endpoint
            )
            total_checks += 1
            response_times[endpoint.name.lower().replace(" ", "_")] = response_time

            if success:
                successful_checks += 1
                logger.info(f"✓ {endpoint.name}: {response_time:.2f}s")
            else:
                failed_checks += 1
                error_msg = f"{endpoint.name}: {error}"
                errors.append(error_msg)
                logger.warning(f"✗ {error_msg}")

                if endpoint.required:
                    if "discord" in endpoint.name.lower():
                        recommended_actions.append("Check Discord service status")
                    else:
                        recommended_actions.append(
                            f"Check {endpoint.name} connectivity"
                        )

        # 3. Check Discord gateways
        logger.info("Checking Discord gateways...")
        working_gateway = await self.find_working_discord_gateway()
        if working_gateway:
            successful_checks += 1
            response_times["discord_gateway"] = (
                0.1  # Will be set by find_working_discord_gateway
            )
        else:
            failed_checks += 1
            errors.append("No working Discord gateways found")
            recommended_actions.append(
                "Check Discord gateway connectivity and firewall settings"
            )
        total_checks += 1

        # Determine overall status
        success_rate = (
            (successful_checks / total_checks) * 100 if total_checks > 0 else 0
        )

        if success_rate >= 90:
            status = ConnectivityStatus.HEALTHY
        elif success_rate >= 60:
            status = ConnectivityStatus.DEGRADED
            recommended_actions.append("Some services may be slow or unreliable")
        else:
            status = ConnectivityStatus.FAILED
            recommended_actions.append("Consider checking network infrastructure")

        result = ConnectivityCheckResult(
            status=status,
            successful_checks=successful_checks,
            failed_checks=failed_checks,
            total_checks=total_checks,
            response_times=response_times,
            errors=errors,
            recommended_actions=recommended_actions,
        )

        logger.info(
            f"Connectivity check complete: {status.value} ({success_rate:.1f}% success rate)"
        )
        return result

    async def check_basic_connectivity(self) -> bool:
        """Quick basic connectivity check with DNS fallback"""
        # First try using our DNS resolution system
        if self.current_dns_server:
            success, _, _ = await self.check_dns_resolution(
                "discord.com", self.current_dns_server
            )
            if success:
                try:
                    # Try a quick HTTP request
                    timeout = aiohttp.ClientTimeout(total=5, connect=3)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(
                            "https://discord.com/api/v10/gateway"
                        ) as response:
                            return response.status < 500
                except Exception as e:
                    logger.debug(f"HTTP check failed but DNS worked: {e}")
                    return True  # DNS working is a good sign

        # Fallback to system DNS resolution
        try:
            # Try to resolve Discord's domain using system DNS
            socket.gethostbyname("discord.com")

            # Try a quick HTTP request
            timeout = aiohttp.ClientTimeout(total=5, connect=3)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://discord.com/api/v10/gateway"
                ) as response:
                    return response.status < 500

        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed in basic connectivity check: {e}")
            return False
        except Exception as e:
            logger.warning(f"Basic connectivity check failed: {e}")
            return False

    def get_optimal_dns_server(self) -> Optional[str]:
        """Get the current optimal DNS server address"""
        return self.current_dns_server.address if self.current_dns_server else None

    def get_optimal_discord_gateway(self) -> Optional[str]:
        """Get the current optimal Discord gateway"""
        return self.current_gateway.endpoint if self.current_gateway else None


class NetworkConnectivityManager:
    """Manages network connectivity for the bot"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.checker = NetworkConnectivityChecker(config)
        self.last_check_time: Optional[float] = None
        self.last_check_result: Optional[ConnectivityCheckResult] = None
        self.connectivity_callbacks: List[callable] = []

    def add_connectivity_callback(self, callback: callable):
        """Add callback to be called when connectivity changes"""
        self.connectivity_callbacks.append(callback)

    async def ensure_connectivity(
        self, skip_cache: bool = False
    ) -> ConnectivityCheckResult:
        """Ensure network connectivity, using cache if recent"""
        current_time = time.time()
        cache_timeout = self.config.get("network", {}).get(
            "check_cache_timeout", 300
        )  # 5 minutes

        # Use cached result if recent and not forcing refresh
        if (
            not skip_cache
            and self.last_check_result
            and self.last_check_time
            and current_time - self.last_check_time < cache_timeout
        ):
            logger.debug("Using cached connectivity check result")
            return self.last_check_result

        # Run fresh connectivity check
        result = await self.checker.run_full_connectivity_check()
        self.last_check_result = result
        self.last_check_time = current_time

        # Notify callbacks if status changed
        for callback in self.connectivity_callbacks:
            try:
                await callback(result)
            except Exception as e:
                logger.error(f"Connectivity callback failed: {e}")

        return result

    async def wait_for_connectivity(
        self, max_wait_time: int = 300, check_interval: int = 30
    ) -> bool:
        """Wait for network connectivity to be restored"""
        logger.info(f"Waiting for network connectivity (max {max_wait_time}s)...")

        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            if await self.checker.check_basic_connectivity():
                logger.info("Network connectivity restored!")
                return True

            logger.info(f"Network still unavailable, waiting {check_interval}s...")
            await asyncio.sleep(check_interval)

        logger.error(f"Network connectivity not restored after {max_wait_time}s")
        return False


# Global connectivity manager instance
_connectivity_manager: Optional[NetworkConnectivityManager] = None


def get_connectivity_manager(
    config: Optional[Dict[str, Any]] = None,
) -> NetworkConnectivityManager:
    """Get the global network connectivity manager"""
    global _connectivity_manager
    if _connectivity_manager is None:
        _connectivity_manager = NetworkConnectivityManager(config)
    return _connectivity_manager


async def run_preflight_checks(config: Optional[Dict[str, Any]] = None) -> bool:
    """Run preflight network checks before starting the bot"""
    logger.info("Running preflight network checks...")

    manager = get_connectivity_manager(config)
    result = await manager.ensure_connectivity(skip_cache=True)

    if result.status == ConnectivityStatus.FAILED:
        logger.error("Preflight checks failed - critical network issues detected")
        logger.error("Errors:")
        for error in result.errors:
            logger.error(f"  - {error}")
        logger.error("Recommended actions:")
        for action in result.recommended_actions:
            logger.error(f"  - {action}")
        return False

    elif result.status == ConnectivityStatus.DEGRADED:
        logger.warning("Preflight checks show degraded connectivity")
        logger.warning("Some services may be slow or unreliable")
        # Continue anyway - bot might still work

    logger.info(
        f"Preflight checks complete: {result.status.value} ({result.success_rate:.1f}% success)"
    )
    return True
