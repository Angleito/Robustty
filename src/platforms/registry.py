import logging
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

from .base import VideoPlatform

if TYPE_CHECKING:
    from ..services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class PlatformRegistry:
    """Registry for video platforms"""

    # Platform mapping will be populated as platforms are imported
    PLATFORMS: Dict[str, Type[VideoPlatform]] = {}

    def __init__(self, cache_manager: Optional['CacheManager'] = None):
        self.platforms: Dict[str, VideoPlatform] = {}
        self.cache_manager = cache_manager

    def register_platform(self, name: str, platform_class: Type[VideoPlatform]) -> None:
        """Register a new platform type"""
        self.PLATFORMS[name] = platform_class
        logger.info(f"Registered platform type: {name}")

    async def load_platforms(self, config: Dict[str, Any]):
        """Load platforms from configuration"""
        for name, platform_config in config.items():
            if platform_config.get("enabled", False):
                if name in self.PLATFORMS:
                    try:
                        # Pass name, config, and cache manager to the constructor
                        platform = self.PLATFORMS[name](name, platform_config, self.cache_manager)
                        await platform.initialize()
                        self.platforms[name] = platform
                        logger.info(f"Loaded platform: {name} (cache: {'enabled' if self.cache_manager else 'disabled'})")
                    except Exception as e:
                        logger.error(f"Failed to load platform {name}: {e}")
                else:
                    logger.warning(f"Unknown platform type: {name}")

    async def cleanup_all(self):
        """Cleanup all platforms"""
        for platform in self.platforms.values():
            await platform.cleanup()

    def get_platform(self, name: str) -> Optional[VideoPlatform]:
        """Get a platform by name"""
        return self.platforms.get(name)

    def get_all_platforms(self) -> Dict[str, VideoPlatform]:
        """Get all loaded platforms"""
        return self.platforms

    def get_enabled_platforms(self) -> Dict[str, VideoPlatform]:
        """Get only enabled platforms"""
        return {
            name: platform
            for name, platform in self.platforms.items()
            if platform.enabled
        }
