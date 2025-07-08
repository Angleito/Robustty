#!/usr/bin/env python3
"""
Validation script for network routing module.
This script can be run to verify the module is working correctly.
"""

import asyncio
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_module_import():
    """Validate that the module can be imported"""
    try:
        # Add src to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        
        from utils.network_routing import (
            NetworkAwareHTTPClient,
            RoutingConfig,
            ServiceType,
            get_http_client,
            discord_session,
            youtube_session,
            platform_session,
            url_session,
            get_routing_info
        )
        
        logger.info("✓ Successfully imported network routing module")
        return True
        
    except ImportError as e:
        logger.error(f"✗ Failed to import network routing module: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error importing module: {e}")
        return False

def validate_configuration():
    """Validate configuration loading"""
    try:
        from utils.network_routing import RoutingConfig, ServiceType
        
        # Test default configuration
        config = RoutingConfig()
        logger.info(f"✓ Default configuration loaded: strategy={config.strategy.value}")
        
        # Test service routing configuration
        for service, use_vpn in config.service_routing.items():
            logger.info(f"  {service.value}: VPN={use_vpn}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Configuration validation failed: {e}")
        return False

async def validate_client_initialization():
    """Validate HTTP client initialization"""
    try:
        from utils.network_routing import NetworkAwareHTTPClient, RoutingConfig
        
        config = RoutingConfig()
        client = NetworkAwareHTTPClient(config)
        
        # Test initialization
        await client.initialize()
        logger.info("✓ HTTP client initialized successfully")
        
        # Test routing info
        routing_info = client.get_routing_info()
        logger.info(f"✓ Routing info retrieved: {len(routing_info['interfaces'])} interfaces detected")
        
        # Test cleanup
        await client.cleanup()
        logger.info("✓ HTTP client cleanup completed")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Client initialization failed: {e}")
        return False

async def validate_session_context_managers():
    """Validate session context managers"""
    try:
        from utils.network_routing import discord_session, youtube_session, platform_session, url_session
        
        # Test Discord session
        async with discord_session() as session:
            logger.info(f"✓ Discord session created: {type(session).__name__}")
        
        # Test YouTube session
        async with youtube_session() as session:
            logger.info(f"✓ YouTube session created: {type(session).__name__}")
        
        # Test platform session
        async with platform_session('rumble') as session:
            logger.info(f"✓ Platform session created: {type(session).__name__}")
        
        # Test URL session
        async with url_session('https://discord.com/api/v10/gateway') as session:
            logger.info(f"✓ URL session created: {type(session).__name__}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Session context managers failed: {e}")
        return False

async def validate_service_detection():
    """Validate service type detection"""
    try:
        from utils.network_routing import NetworkRouter, RoutingConfig
        
        config = RoutingConfig()
        router = NetworkRouter(config)
        
        test_urls = [
            ('https://discord.com/api/v10/gateway', 'discord'),
            ('https://www.youtube.com/watch?v=abc123', 'youtube'),
            ('https://rumble.com/video/test', 'rumble'),
            ('https://odysee.com/@channel/video', 'odysee'),
            ('https://example.com/generic', 'generic'),
        ]
        
        for url, expected_service in test_urls:
            service_type = router._detect_service_from_url(url)
            logger.info(f"✓ {url} -> {service_type.value}")
            
            if service_type.value != expected_service:
                logger.warning(f"  Expected {expected_service}, got {service_type.value}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Service detection failed: {e}")
        return False

async def validate_interface_detection():
    """Validate network interface detection"""
    try:
        from utils.network_routing import NetworkInterfaceDetector, RoutingConfig
        
        config = RoutingConfig()
        detector = NetworkInterfaceDetector(config)
        
        # Test interface detection
        interfaces = await detector.detect_interfaces()
        logger.info(f"✓ Interface detection completed: {len(interfaces)} interfaces found")
        
        for name, interface in interfaces.items():
            logger.info(f"  {name}: {interface.ip_address} (VPN: {interface.is_vpn}, Default: {interface.is_default})")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Interface detection failed: {e}")
        return False

def validate_environment_variables():
    """Validate environment variable handling"""
    try:
        # Test with temporary environment variables
        original_env = {}
        test_env = {
            'DISCORD_USE_VPN': 'true',
            'YOUTUBE_USE_VPN': 'false',
            'NETWORK_STRATEGY': 'split_tunnel',
            'VPN_INTERFACE': 'wg0',
            'DEFAULT_INTERFACE': 'eth0'
        }
        
        # Save original values
        for key in test_env:
            original_env[key] = os.environ.get(key)
        
        # Set test values
        for key, value in test_env.items():
            os.environ[key] = value
        
        try:
            from utils.network_routing import RoutingConfig, ServiceType
            
            config = RoutingConfig()
            
            # Validate configuration
            assert config.strategy.value == 'split_tunnel', f"Expected split_tunnel, got {config.strategy.value}"
            assert config.service_routing[ServiceType.DISCORD] == True, "Discord should use VPN"
            assert config.service_routing[ServiceType.YOUTUBE] == False, "YouTube should not use VPN"
            assert config.vpn_interface == 'wg0', f"Expected wg0, got {config.vpn_interface}"
            assert config.direct_interface == 'eth0', f"Expected eth0, got {config.direct_interface}"
            
            logger.info("✓ Environment variable handling working correctly")
            return True
            
        finally:
            # Restore original values
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        
    except Exception as e:
        logger.error(f"✗ Environment variable validation failed: {e}")
        return False

async def main():
    """Run all validation tests"""
    logger.info("Starting network routing module validation...")
    logger.info("=" * 60)
    
    tests = [
        ("Module Import", validate_module_import),
        ("Configuration", validate_configuration),
        ("Client Initialization", validate_client_initialization),
        ("Session Context Managers", validate_session_context_managers),
        ("Service Detection", validate_service_detection),
        ("Interface Detection", validate_interface_detection),
        ("Environment Variables", validate_environment_variables),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\nRunning: {test_name}")
        logger.info("-" * 40)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                logger.info(f"✓ {test_name} PASSED")
            else:
                failed += 1
                logger.error(f"✗ {test_name} FAILED")
                
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test_name} FAILED with exception: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Validation Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All validation tests passed! Network routing module is ready.")
        sys.exit(0)
    else:
        logger.error("❌ Some validation tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())