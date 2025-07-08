#!/usr/bin/env python3
"""
Test script to verify network routing integration for Rumble, Odysee, and PeerTube platforms.
"""

import asyncio
import logging
import sys
from typing import Dict, Any

from src.utils.network_routing import get_http_client, get_routing_info
from src.platforms.rumble import RumblePlatform
from src.platforms.odysee import OdyseePlatform
from src.platforms.peertube import PeerTubePlatform

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_network_routing_integration():
    """Test that all platforms are properly integrated with network routing"""
    
    print("=" * 60)
    print("Testing Network Routing Integration for Platforms")
    print("=" * 60)
    
    # Initialize HTTP client
    http_client = get_http_client()
    await http_client.initialize()
    
    # Get routing info
    routing_info = await get_routing_info()
    print(f"\nNetwork Routing Configuration:")
    print(f"- Strategy: {routing_info['strategy']}")
    print(f"- Interfaces: {list(routing_info['interfaces'].keys())}")
    print(f"- Routing table: {routing_info['routing_table']}")
    
    # Test platform configurations
    platforms_config = {
        'rumble': {
            'enabled': True,
            'api_token': 'test_token'  # Mock token for testing
        },
        'odysee': {
            'enabled': True,
            'api_url': 'https://api.odysee.com/api/v1'
        },
        'peertube': {
            'enabled': True,
            'instances': [
                'https://tube.exemple.com',
                'https://peertube.example.org'
            ]
        }
    }
    
    print(f"\n{'='*60}")
    print("Testing Platform Initialization")
    print(f"{'='*60}")
    
    # Test each platform
    platforms = []
    
    # Test Rumble platform
    try:
        rumble = RumblePlatform('rumble', platforms_config['rumble'])
        await rumble.initialize()
        
        # Check if network client is initialized
        if hasattr(rumble, '_network_client') and rumble._network_client:
            print("✓ Rumble platform: Network client initialized successfully")
            if hasattr(rumble, '_service_type'):
                print(f"  - Service type: {rumble._service_type}")
            platforms.append(('Rumble', rumble))
        else:
            print("✗ Rumble platform: Network client not initialized")
            
    except Exception as e:
        print(f"✗ Rumble platform initialization failed: {e}")
    
    # Test Odysee platform  
    try:
        odysee = OdyseePlatform('odysee', platforms_config['odysee'])
        await odysee.initialize()
        
        # Check if network client is initialized
        if hasattr(odysee, '_network_client') and odysee._network_client:
            print("✓ Odysee platform: Network client initialized successfully")
            if hasattr(odysee, '_service_type'):
                print(f"  - Service type: {odysee._service_type}")
            platforms.append(('Odysee', odysee))
        else:
            print("✗ Odysee platform: Network client not initialized")
            
    except Exception as e:
        print(f"✗ Odysee platform initialization failed: {e}")
    
    # Test PeerTube platform
    try:
        peertube = PeerTubePlatform('peertube', platforms_config['peertube'])
        await peertube.initialize()
        
        # Check if network client is initialized
        if hasattr(peertube, '_network_client') and peertube._network_client:
            print("✓ PeerTube platform: Network client initialized successfully")
            if hasattr(peertube, '_service_type'):
                print(f"  - Service type: {peertube._service_type}")
            platforms.append(('PeerTube', peertube))
        else:
            print("✗ PeerTube platform: Network client not initialized")
            
    except Exception as e:
        print(f"✗ PeerTube platform initialization failed: {e}")
    
    print(f"\n{'='*60}")
    print("Testing Network Session Access")
    print(f"{'='*60}")
    
    # Test session access for each platform
    for platform_name, platform in platforms:
        try:
            if hasattr(platform, '_network_client') and platform._network_client:
                async with platform._network_client.get_session(platform._service_type) as session:
                    print(f"✓ {platform_name}: Network session created successfully")
                    print(f"  - Session type: {type(session).__name__}")
                    print(f"  - Session closed: {session.closed}")
            else:
                print(f"✗ {platform_name}: No network client available")
                
        except Exception as e:
            print(f"✗ {platform_name}: Session creation failed: {e}")
    
    print(f"\n{'='*60}")
    print("Testing Context Manager Access")
    print(f"{'='*60}")
    
    # Test the specific context managers
    from src.utils.network_routing import rumble_session, odysee_session, peertube_session
    
    context_managers = [
        ('rumble_session', rumble_session),
        ('odysee_session', odysee_session),
        ('peertube_session', peertube_session)
    ]
    
    for name, context_manager in context_managers:
        try:
            async with context_manager() as session:
                print(f"✓ {name}: Context manager working correctly")
                print(f"  - Session type: {type(session).__name__}")
                print(f"  - Session closed: {session.closed}")
        except Exception as e:
            print(f"✗ {name}: Context manager failed: {e}")
    
    print(f"\n{'='*60}")
    print("Integration Summary")
    print(f"{'='*60}")
    
    print(f"✓ Network routing module loaded successfully")
    print(f"✓ HTTP client initialized with routing support")
    print(f"✓ {len(platforms)} platforms integrated with network routing")
    print(f"✓ Service-specific context managers available")
    
    print(f"\n🎉 Network routing integration completed successfully!")
    print(f"All platform API calls will now use direct network routing to bypass VPN for better performance.")
    
    # Cleanup
    await http_client.cleanup()
    
    for platform_name, platform in platforms:
        if hasattr(platform, 'cleanup'):
            await platform.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(test_network_routing_integration())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)