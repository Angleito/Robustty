from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class BotConfig(BaseModel):
    command_prefix: str = Field(default="!")
    description: str = Field(default="Multi-platform music bot")
    activity: str = Field(default="music from everywhere")

class PlatformConfig(BaseModel):
    enabled: bool = Field(default=True)
    api_key: Optional[str] = None
    max_results: int = Field(default=10)
    quota_limit: int = Field(default=10000)
    quota_conservation: bool = Field(default=True)

class PerformanceConfig(BaseModel):
    search_timeout: int = Field(default=30)
    stream_timeout: int = Field(default=300)
    max_queue_size: int = Field(default=100)

class CacheConfig(BaseModel):
    enabled: bool = Field(default=False)
    url: str = Field(default="redis://localhost:6379")
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = None
    ttl: Dict[str, int] = Field(default_factory=lambda: {"metadata": 3600, "stream": 1800, "search": 1800})

class HealthMonitorConfig(BaseModel):
    enabled: bool = Field(default=True)
    check_interval: int = Field(default=30)
    max_consecutive_failures: int = Field(default=3)

class FallbacksConfig(BaseModel):
    enabled: bool = Field(default=True)
    max_fallback_duration_hours: int = Field(default=24)
    retry_interval_minutes: int = Field(default=30)

class HealthEndpointsConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8081)

class NetworkConfig(BaseModel):
    dns_servers: List[Dict[str, Any]] = Field(default_factory=list)
    discord_gateways: List[Dict[str, Any]] = Field(default_factory=list)
    essential_endpoints: List[Dict[str, Any]] = Field(default_factory=list)
    check_cache_timeout: int = Field(default=300)

class CookiesConfig(BaseModel):
    pass

class Config(BaseModel):
    bot: BotConfig
    platforms: Dict[str, PlatformConfig]
    performance: PerformanceConfig
    cache: CacheConfig
    health_monitor: HealthMonitorConfig
    fallbacks: FallbacksConfig
    health_endpoints: HealthEndpointsConfig
    network: NetworkConfig
    cookies: CookiesConfig
