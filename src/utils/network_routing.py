"""
Network-aware HTTP client module for service-specific routing.

This module provides intelligent network routing for different services,
allowing traffic to be routed through different network interfaces based
on service type and configuration. It supports VPN routing for Discord
while keeping API calls on the direct connection.
"""

import asyncio
import logging
import os
import socket
import subprocess
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Service types for routing decisions"""
    
    DISCORD = "discord"
    YOUTUBE = "youtube"
    RUMBLE = "rumble"
    ODYSEE = "odysee"
    PEERTUBE = "peertube"
    GENERIC = "generic"


class NetworkStrategy(Enum):
    """Network routing strategies"""
    
    AUTO = "auto"  # Automatically detect best routing
    VPN_ONLY = "vpn_only"  # Route everything through VPN
    DIRECT_ONLY = "direct_only"  # Route everything directly
    SPLIT_TUNNEL = "split_tunnel"  # Service-specific routing


@dataclass
class NetworkInterface:
    """Network interface configuration"""
    
    name: str
    ip_address: str
    subnet: str
    gateway: Optional[str] = None
    is_vpn: bool = False
    is_default: bool = False
    mtu: int = 1500
    route_mark: Optional[int] = None
    
    def __post_init__(self):
        """Validate interface configuration"""
        if self.is_vpn and not self.route_mark:
            logger.warning(f"VPN interface {self.name} has no route mark configured")


@dataclass
class RoutingConfig:
    """Configuration for network routing"""
    
    strategy: NetworkStrategy = NetworkStrategy.AUTO
    service_routing: Dict[ServiceType, bool] = field(default_factory=dict)
    vpn_interface: Optional[str] = None
    direct_interface: Optional[str] = None
    fallback_to_default: bool = True
    dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    
    def __post_init__(self):
        """Load configuration from environment"""
        self.strategy = NetworkStrategy(os.getenv("NETWORK_STRATEGY", "auto"))
        
        # Load service-specific routing configuration
        self.service_routing = {
            ServiceType.DISCORD: self._get_service_vpn_setting("DISCORD_USE_VPN"),
            ServiceType.YOUTUBE: self._get_service_vpn_setting("YOUTUBE_USE_VPN"),
            ServiceType.RUMBLE: self._get_service_vpn_setting("RUMBLE_USE_VPN"),
            ServiceType.ODYSEE: self._get_service_vpn_setting("ODYSEE_USE_VPN"),
            ServiceType.PEERTUBE: self._get_service_vpn_setting("PEERTUBE_USE_VPN"),
        }
        
        # Load interface names
        self.vpn_interface = os.getenv("VPN_INTERFACE", "auto")
        self.direct_interface = os.getenv("DEFAULT_INTERFACE", "auto")
        
        # Load DNS configuration
        custom_dns = os.getenv("VPN_DNS")
        if custom_dns:
            self.dns_servers = [custom_dns] + self.dns_servers
    
    def _get_service_vpn_setting(self, env_var: str) -> bool:
        """Get service VPN setting from environment"""
        value = os.getenv(env_var, "false").lower()
        return value in ("true", "1", "yes", "on")


class NetworkInterfaceDetector:
    """Detects and manages network interfaces"""
    
    def __init__(self, config: RoutingConfig):
        self.config = config
        self._interfaces: Dict[str, NetworkInterface] = {}
        self._detected_interfaces: Optional[Dict[str, NetworkInterface]] = None
        
    async def detect_interfaces(self) -> Dict[str, NetworkInterface]:
        """Detect available network interfaces"""
        if self._detected_interfaces is not None:
            return self._detected_interfaces
            
        interfaces = {}
        
        try:
            # Try to detect Docker network interfaces first
            docker_interfaces = await self._detect_docker_interfaces()
            interfaces.update(docker_interfaces)
            
            # Detect system interfaces
            system_interfaces = await self._detect_system_interfaces()
            interfaces.update(system_interfaces)
            
            # Mark VPN and direct interfaces
            await self._classify_interfaces(interfaces)
            
            self._detected_interfaces = interfaces
            logger.info(f"Detected {len(interfaces)} network interfaces")
            
            for name, interface in interfaces.items():
                logger.debug(f"Interface {name}: {interface.ip_address} "
                           f"(VPN: {interface.is_vpn}, Default: {interface.is_default})")
                           
        except Exception as e:
            logger.error(f"Failed to detect network interfaces: {e}")
            # Create a default interface as fallback
            interfaces["default"] = NetworkInterface(
                name="default",
                ip_address="0.0.0.0",
                subnet="0.0.0.0/0",
                is_default=True
            )
            
        return interfaces
    
    async def _detect_docker_interfaces(self) -> Dict[str, NetworkInterface]:
        """Detect Docker network interfaces"""
        interfaces = {}
        
        try:
            # Check for Docker networks based on environment configuration
            vpn_subnet = os.getenv("VPN_NETWORK_SUBNET", "172.28.0.0/16")
            direct_subnet = os.getenv("DIRECT_NETWORK_SUBNET", "172.29.0.0/16")
            
            # Try to get container IP addresses
            result = await self._run_command(["hostname", "-I"])
            if result:
                ips = result.strip().split()
                
                for ip in ips:
                    if self._ip_in_subnet(ip, vpn_subnet):
                        interfaces["vpn"] = NetworkInterface(
                            name="vpn",
                            ip_address=ip,
                            subnet=vpn_subnet,
                            is_vpn=True,
                            route_mark=int(os.getenv("VPN_ROUTE_MARK", "100"))
                        )
                    elif self._ip_in_subnet(ip, direct_subnet):
                        interfaces["direct"] = NetworkInterface(
                            name="direct",
                            ip_address=ip,
                            subnet=direct_subnet,
                            is_default=True
                        )
                        
        except Exception as e:
            logger.debug(f"Docker interface detection failed: {e}")
            
        return interfaces
    
    async def _detect_system_interfaces(self) -> Dict[str, NetworkInterface]:
        """Detect system network interfaces"""
        interfaces = {}
        
        try:
            # Use hostname to get IP addresses
            result = await self._run_command(["hostname", "-I"])
            if result:
                ips = result.strip().split()
                
                # Get the first IP as default
                if ips:
                    interfaces["system"] = NetworkInterface(
                        name="system",
                        ip_address=ips[0],
                        subnet="0.0.0.0/0",
                        is_default=True
                    )
                    
        except Exception as e:
            logger.debug(f"System interface detection failed: {e}")
            
        return interfaces
    
    async def _classify_interfaces(self, interfaces: Dict[str, NetworkInterface]):
        """Classify interfaces as VPN or direct"""
        vpn_indicators = ["wg", "tun", "vpn", "proton"]
        
        for name, interface in interfaces.items():
            # Check if interface name indicates VPN
            if any(indicator in name.lower() for indicator in vpn_indicators):
                interface.is_vpn = True
                
            # Check if IP is in private ranges (potential VPN)
            if self._is_private_ip(interface.ip_address):
                if "172.28." in interface.ip_address:  # Common VPN range
                    interface.is_vpn = True
    
    def _ip_in_subnet(self, ip: str, subnet: str) -> bool:
        """Check if IP is in subnet"""
        try:
            import ipaddress
            return ipaddress.ip_address(ip) in ipaddress.ip_network(subnet)
        except Exception:
            return False
    
    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is in private range"""
        try:
            import ipaddress
            return ipaddress.ip_address(ip).is_private
        except Exception:
            return False
    
    async def _run_command(self, cmd: List[str]) -> Optional[str]:
        """Run shell command and return output"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.debug(f"Command {' '.join(cmd)} failed: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.debug(f"Failed to run command {' '.join(cmd)}: {e}")
            return None


class NetworkRouter:
    """Manages network routing for different services"""
    
    def __init__(self, config: RoutingConfig):
        self.config = config
        self.detector = NetworkInterfaceDetector(config)
        self.interfaces: Dict[str, NetworkInterface] = {}
        self._routing_table: Dict[ServiceType, NetworkInterface] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize network routing"""
        if self._initialized:
            return
            
        try:
            # Detect available interfaces
            self.interfaces = await self.detector.detect_interfaces()
            
            # Build routing table
            await self._build_routing_table()
            
            self._initialized = True
            logger.info("Network routing initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize network routing: {e}")
            # Create default routing as fallback
            self._create_default_routing()
    
    async def _build_routing_table(self):
        """Build routing table based on configuration"""
        # Find VPN and direct interfaces
        vpn_interface = self._find_vpn_interface()
        direct_interface = self._find_direct_interface()
        
        # Route services based on configuration
        for service_type, use_vpn in self.config.service_routing.items():
            if use_vpn and vpn_interface:
                self._routing_table[service_type] = vpn_interface
                logger.debug(f"Routing {service_type.value} through VPN: {vpn_interface.name}")
            elif direct_interface:
                self._routing_table[service_type] = direct_interface
                logger.debug(f"Routing {service_type.value} through direct: {direct_interface.name}")
            else:
                # Fallback to default
                default_interface = self._find_default_interface()
                if default_interface:
                    self._routing_table[service_type] = default_interface
                    logger.debug(f"Routing {service_type.value} through default: {default_interface.name}")
    
    def _find_vpn_interface(self) -> Optional[NetworkInterface]:
        """Find the VPN interface"""
        # Look for explicitly configured VPN interface
        if self.config.vpn_interface != "auto":
            return self.interfaces.get(self.config.vpn_interface)
        
        # Auto-detect VPN interface
        for interface in self.interfaces.values():
            if interface.is_vpn:
                return interface
        
        return None
    
    def _find_direct_interface(self) -> Optional[NetworkInterface]:
        """Find the direct interface"""
        # Look for explicitly configured direct interface
        if self.config.direct_interface != "auto":
            return self.interfaces.get(self.config.direct_interface)
        
        # Auto-detect direct interface
        for interface in self.interfaces.values():
            if not interface.is_vpn and interface.is_default:
                return interface
        
        return None
    
    def _find_default_interface(self) -> Optional[NetworkInterface]:
        """Find the default interface"""
        for interface in self.interfaces.values():
            if interface.is_default:
                return interface
        
        # Return any available interface
        return next(iter(self.interfaces.values()), None)
    
    def _create_default_routing(self):
        """Create default routing when detection fails"""
        default_interface = NetworkInterface(
            name="default",
            ip_address="0.0.0.0",
            subnet="0.0.0.0/0",
            is_default=True
        )
        
        for service_type in ServiceType:
            self._routing_table[service_type] = default_interface
    
    def get_interface_for_service(self, service_type: ServiceType) -> Optional[NetworkInterface]:
        """Get the network interface for a service"""
        return self._routing_table.get(service_type)
    
    def get_interface_for_url(self, url: str) -> Optional[NetworkInterface]:
        """Get the network interface for a URL based on service detection"""
        service_type = self._detect_service_from_url(url)
        return self.get_interface_for_service(service_type)
    
    def _detect_service_from_url(self, url: str) -> ServiceType:
        """Detect service type from URL"""
        try:
            domain = urlparse(url).netloc.lower()
            
            if any(d in domain for d in ["discord.com", "discordapp.com", "discord.gg"]):
                return ServiceType.DISCORD
            elif any(d in domain for d in ["youtube.com", "youtu.be", "googleapis.com"]):
                return ServiceType.YOUTUBE
            elif "rumble.com" in domain:
                return ServiceType.RUMBLE
            elif "odysee.com" in domain:
                return ServiceType.ODYSEE
            elif "peertube" in domain:
                return ServiceType.PEERTUBE
            else:
                return ServiceType.GENERIC
                
        except Exception as e:
            logger.debug(f"Failed to detect service from URL {url}: {e}")
            return ServiceType.GENERIC


class NetworkAwareHTTPClient:
    """HTTP client with network-aware routing"""
    
    def __init__(self, config: Optional[RoutingConfig] = None):
        self.config = config or RoutingConfig()
        self.router = NetworkRouter(self.config)
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the HTTP client"""
        if self._initialized:
            return
            
        await self.router.initialize()
        self._initialized = True
        logger.info("Network-aware HTTP client initialized")
    
    async def cleanup(self):
        """Clean up HTTP sessions"""
        for session in self._sessions.values():
            if not session.closed:
                await session.close()
        self._sessions.clear()
        logger.info("Network-aware HTTP client cleaned up")
    
    @asynccontextmanager
    async def get_session(self, service_type: ServiceType, **session_kwargs):
        """Get a session configured for the service type"""
        if not self._initialized:
            await self.initialize()
        
        interface = self.router.get_interface_for_service(service_type)
        session_key = f"{service_type.value}_{interface.name if interface else 'default'}"
        
        if session_key not in self._sessions:
            self._sessions[session_key] = await self._create_session(interface, **session_kwargs)
        
        session = self._sessions[session_key]
        
        try:
            yield session
        except Exception as e:
            logger.error(f"Error in HTTP session for {service_type.value}: {e}")
            raise
    
    @asynccontextmanager
    async def get_session_for_url(self, url: str, **session_kwargs):
        """Get a session configured for the URL's service"""
        service_type = self.router._detect_service_from_url(url)
        async with self.get_session(service_type, **session_kwargs) as session:
            yield session
    
    async def _create_session(self, interface: Optional[NetworkInterface], **session_kwargs) -> aiohttp.ClientSession:
        """Create HTTP session with interface-specific configuration"""
        # Default session configuration
        timeout = session_kwargs.pop('timeout', aiohttp.ClientTimeout(total=30, connect=10))
        
        # Create connector with interface-specific settings
        connector_kwargs = {
            'limit_per_host': 10,
            'ttl_dns_cache': 300,
            'use_dns_cache': True,
        }
        
        # Configure interface binding if available
        if interface and interface.ip_address != "0.0.0.0":
            try:
                connector_kwargs['local_addr'] = (interface.ip_address, 0)
                logger.debug(f"Binding session to interface {interface.name} ({interface.ip_address})")
            except Exception as e:
                logger.warning(f"Failed to bind to interface {interface.name}: {e}")
        
        # Create connector
        connector = aiohttp.TCPConnector(**connector_kwargs)
        
        # Create session
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            **session_kwargs
        )
        
        return session
    
    def get_routing_info(self) -> Dict[str, Any]:
        """Get current routing information"""
        return {
            'strategy': self.config.strategy.value,
            'interfaces': {
                name: {
                    'ip': interface.ip_address,
                    'subnet': interface.subnet,
                    'is_vpn': interface.is_vpn,
                    'is_default': interface.is_default
                }
                for name, interface in self.router.interfaces.items()
            },
            'routing_table': {
                service.value: interface.name
                for service, interface in self.router._routing_table.items()
            }
        }


# Global HTTP client instance
_http_client: Optional[NetworkAwareHTTPClient] = None


def get_http_client(config: Optional[RoutingConfig] = None) -> NetworkAwareHTTPClient:
    """Get the global network-aware HTTP client"""
    global _http_client
    if _http_client is None:
        _http_client = NetworkAwareHTTPClient(config)
    return _http_client


async def initialize_http_client(config: Optional[RoutingConfig] = None):
    """Initialize the global HTTP client"""
    client = get_http_client(config)
    await client.initialize()


async def cleanup_http_client():
    """Clean up the global HTTP client"""
    global _http_client
    if _http_client:
        await _http_client.cleanup()
        _http_client = None


# Convenience functions for common service types
@asynccontextmanager
async def discord_session(**kwargs):
    """Get HTTP session for Discord services"""
    client = get_http_client()
    async with client.get_session(ServiceType.DISCORD, **kwargs) as session:
        yield session


@asynccontextmanager
async def youtube_session(**kwargs):
    """Get HTTP session for YouTube services"""
    client = get_http_client()
    async with client.get_session(ServiceType.YOUTUBE, **kwargs) as session:
        yield session


@asynccontextmanager
async def platform_session(platform_name: str, **kwargs):
    """Get HTTP session for a specific platform"""
    client = get_http_client()
    
    # Map platform names to service types
    platform_mapping = {
        'youtube': ServiceType.YOUTUBE,
        'rumble': ServiceType.RUMBLE,
        'odysee': ServiceType.ODYSEE,
        'peertube': ServiceType.PEERTUBE,
    }
    
    service_type = platform_mapping.get(platform_name.lower(), ServiceType.GENERIC)
    async with client.get_session(service_type, **kwargs) as session:
        yield session


@asynccontextmanager
async def rumble_session(**kwargs):
    """Get HTTP session for Rumble services with direct network routing"""
    client = get_http_client()
    async with client.get_session(ServiceType.RUMBLE, **kwargs) as session:
        yield session


@asynccontextmanager
async def odysee_session(**kwargs):
    """Get HTTP session for Odysee services with direct network routing"""
    client = get_http_client()
    async with client.get_session(ServiceType.ODYSEE, **kwargs) as session:
        yield session


@asynccontextmanager
async def peertube_session(**kwargs):
    """Get HTTP session for PeerTube services with direct network routing"""
    client = get_http_client()
    async with client.get_session(ServiceType.PEERTUBE, **kwargs) as session:
        yield session


@asynccontextmanager
async def url_session(url: str, **kwargs):
    """Get HTTP session for a specific URL"""
    client = get_http_client()
    async with client.get_session_for_url(url, **kwargs) as session:
        yield session


async def get_routing_info() -> Dict[str, Any]:
    """Get current routing information"""
    client = get_http_client()
    if not client._initialized:
        await client.initialize()
    return client.get_routing_info()