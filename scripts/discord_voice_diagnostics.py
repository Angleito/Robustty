#!/usr/bin/env python3
"""
Discord Voice Connection Diagnostics
Advanced Python-based diagnostics for Discord 4006 voice connection errors
"""

import asyncio
import aiohttp
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiscordVoiceDiagnostics:
    """Discord voice connection diagnostic tools"""
    
    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv('DISCORD_TOKEN')
        self.session: Optional[aiohttp.ClientSession] = None
        self.results: Dict = {
            'timestamp': datetime.now().isoformat(),
            'discord_status': {},
            'voice_regions': {},
            'bot_info': {},
            'permissions': {},
            'connectivity': {},
            'recommendations': []
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def check_discord_api_status(self) -> Dict:
        """Check Discord API and voice server status"""
        logger.info("Checking Discord API status...")
        
        status_endpoints = {
            'status': 'https://discordstatus.com/api/v2/status.json',
            'incidents': 'https://discordstatus.com/api/v2/incidents.json',
            'components': 'https://discordstatus.com/api/v2/components.json'
        }
        
        status_results = {}
        
        for endpoint_name, url in status_endpoints.items():
            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        status_results[endpoint_name] = {
                            'success': True,
                            'data': data,
                            'status_code': response.status
                        }
                        
                        if endpoint_name == 'status':
                            overall_status = data.get('status', {}).get('description', 'Unknown')
                            logger.info(f"Discord overall status: {overall_status}")
                        
                        elif endpoint_name == 'incidents':
                            incidents = data.get('incidents', [])
                            active_incidents = [i for i in incidents if i.get('status') not in ['resolved', 'postmortem']]
                            if active_incidents:
                                logger.warning(f"Active incidents: {len(active_incidents)}")
                                for incident in active_incidents[:3]:  # Show first 3
                                    logger.warning(f"  - {incident.get('name', 'Unknown incident')}")
                            else:
                                logger.info("No active incidents")
                        
                        elif endpoint_name == 'components':
                            components = data.get('components', [])
                            voice_components = [c for c in components if 'voice' in c.get('name', '').lower()]
                            for component in voice_components:
                                status = component.get('status', 'unknown')
                                name = component.get('name', 'Unknown component')
                                logger.info(f"Voice component '{name}': {status}")
                    
                    else:
                        status_results[endpoint_name] = {
                            'success': False,
                            'status_code': response.status,
                            'error': f'HTTP {response.status}'
                        }
                        logger.error(f"Failed to fetch {endpoint_name}: HTTP {response.status}")
            
            except Exception as e:
                status_results[endpoint_name] = {
                    'success': False,
                    'error': str(e),
                    'exception_type': type(e).__name__
                }
                logger.error(f"Error fetching {endpoint_name}: {e}")
        
        self.results['discord_status'] = status_results
        return status_results
    
    async def test_voice_regions(self) -> Dict:
        """Test Discord voice regions and their connectivity"""
        logger.info("Testing Discord voice regions...")
        
        # Get available voice regions from Discord API
        voice_regions_url = "https://discord.com/api/v9/voice/regions"
        
        try:
            async with self.session.get(voice_regions_url, timeout=10) as response:
                if response.status == 200:
                    regions_data = await response.json()
                    logger.info(f"Found {len(regions_data)} voice regions")
                else:
                    logger.error(f"Failed to fetch voice regions: HTTP {response.status}")
                    return {'success': False, 'error': f'HTTP {response.status}'}
        
        except Exception as e:
            logger.error(f"Error fetching voice regions: {e}")
            return {'success': False, 'error': str(e)}
        
        # Test connectivity to each region
        region_results = {}
        
        for region in regions_data:
            region_id = region.get('id', 'unknown')
            region_name = region.get('name', 'Unknown')
            custom = region.get('custom', False)
            deprecated = region.get('deprecated', False)
            optimal = region.get('optimal', False)
            
            logger.info(f"Testing region: {region_name} ({region_id})")
            
            region_result = {
                'id': region_id,
                'name': region_name,
                'custom': custom,
                'deprecated': deprecated,
                'optimal': optimal,
                'connectivity': {}
            }
            
            # Test latency to region if we have an endpoint
            if 'endpoint' in region:
                endpoint = region['endpoint']
                region_result['endpoint'] = endpoint
                
                # Test HTTP connectivity
                try:
                    start_time = time.time()
                    test_url = f"https://{endpoint}/"
                    async with self.session.get(test_url, timeout=5) as response:
                        latency = round((time.time() - start_time) * 1000, 2)
                        region_result['connectivity'] = {
                            'reachable': True,
                            'latency_ms': latency,
                            'status_code': response.status
                        }
                        logger.info(f"  {region_name}: {latency}ms (HTTP {response.status})")
                
                except Exception as e:
                    region_result['connectivity'] = {
                        'reachable': False,
                        'error': str(e),
                        'exception_type': type(e).__name__
                    }
                    logger.warning(f"  {region_name}: Connection failed - {e}")
            
            region_results[region_id] = region_result
        
        # Analyze results
        reachable_count = sum(1 for r in region_results.values() if r['connectivity'].get('reachable', False))
        total_count = len(region_results)
        
        logger.info(f"Voice region connectivity: {reachable_count}/{total_count} reachable")
        
        if reachable_count == 0:
            logger.error("No voice regions are reachable - severe connectivity issue")
        elif reachable_count < total_count * 0.5:
            logger.warning("Less than 50% of voice regions are reachable")
        
        # Find optimal regions
        optimal_regions = [r for r in region_results.values() if r.get('optimal', False)]
        if optimal_regions:
            for region in optimal_regions:
                if region['connectivity'].get('reachable', False):
                    latency = region['connectivity'].get('latency_ms', 'unknown')
                    logger.info(f"Optimal region {region['name']}: {latency}ms")
        
        self.results['voice_regions'] = region_results
        return region_results
    
    async def check_bot_info(self) -> Dict:
        """Get bot information and permissions if token is available"""
        if not self.bot_token:
            logger.warning("No Discord token provided - skipping bot info check")
            return {'success': False, 'error': 'No token provided'}
        
        logger.info("Checking bot information...")
        
        headers = {
            'Authorization': f'Bot {self.bot_token}',
            'Content-Type': 'application/json'
        }
        
        bot_info = {}
        
        # Get bot user info
        try:
            async with self.session.get('https://discord.com/api/v9/users/@me', headers=headers, timeout=10) as response:
                if response.status == 200:
                    user_data = await response.json()
                    bot_info['user'] = {
                        'id': user_data.get('id'),
                        'username': user_data.get('username'),
                        'discriminator': user_data.get('discriminator'),
                        'bot': user_data.get('bot', False),
                        'verified': user_data.get('verified', False)
                    }
                    logger.info(f"Bot: {user_data.get('username')}#{user_data.get('discriminator')}")
                
                elif response.status == 401:
                    logger.error("Bot token is invalid or expired")
                    bot_info['error'] = 'Invalid token'
                
                else:
                    logger.error(f"Failed to get bot info: HTTP {response.status}")
                    bot_info['error'] = f'HTTP {response.status}'
        
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            bot_info['error'] = str(e)
        
        # Get bot guilds (limited info)
        try:
            async with self.session.get('https://discord.com/api/v9/users/@me/guilds', headers=headers, timeout=10) as response:
                if response.status == 200:
                    guilds_data = await response.json()
                    bot_info['guilds'] = {
                        'count': len(guilds_data),
                        'guild_ids': [g.get('id') for g in guilds_data[:10]]  # First 10 guild IDs only
                    }
                    logger.info(f"Bot is in {len(guilds_data)} guilds")
                
                else:
                    logger.warning(f"Could not get guild list: HTTP {response.status}")
        
        except Exception as e:
            logger.warning(f"Error getting guild list: {e}")
        
        self.results['bot_info'] = bot_info
        return bot_info
    
    async def test_websocket_connectivity(self) -> Dict:
        """Test Discord gateway WebSocket connectivity"""
        logger.info("Testing Discord WebSocket connectivity...")
        
        gateway_results = {}
        
        try:
            # Get gateway info
            async with self.session.get('https://discord.com/api/v9/gateway', timeout=10) as response:
                if response.status == 200:
                    gateway_data = await response.json()
                    gateway_url = gateway_data.get('url', 'wss://gateway.discord.gg')
                    
                    logger.info(f"Gateway URL: {gateway_url}")
                    
                    # Test WebSocket connection
                    try:
                        async with self.session.ws_connect(gateway_url, timeout=10) as ws:
                            gateway_results = {
                                'success': True,
                                'gateway_url': gateway_url,
                                'connection_established': True
                            }
                            logger.info("WebSocket connection to gateway successful")
                    
                    except Exception as ws_error:
                        gateway_results = {
                            'success': False,
                            'gateway_url': gateway_url,
                            'connection_established': False,
                            'error': str(ws_error)
                        }
                        logger.error(f"WebSocket connection failed: {ws_error}")
                
                else:
                    gateway_results = {
                        'success': False,
                        'error': f'HTTP {response.status}'
                    }
                    logger.error(f"Failed to get gateway info: HTTP {response.status}")
        
        except Exception as e:
            gateway_results = {
                'success': False,
                'error': str(e),
                'exception_type': type(e).__name__
            }
            logger.error(f"Error testing WebSocket connectivity: {e}")
        
        self.results['connectivity']['websocket'] = gateway_results
        return gateway_results
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on diagnostic results"""
        recommendations = []
        
        # Check Discord status issues
        discord_status = self.results.get('discord_status', {})
        if not discord_status.get('status', {}).get('success', False):
            recommendations.append("❌ Discord API status check failed - verify internet connectivity")
        
        incidents = discord_status.get('incidents', {})
        if incidents.get('success', False):
            incident_data = incidents.get('data', {})
            active_incidents = [i for i in incident_data.get('incidents', []) if i.get('status') not in ['resolved', 'postmortem']]
            if active_incidents:
                recommendations.append("⚠️  Active Discord incidents detected - check https://discordstatus.com")
        
        # Check voice region connectivity
        voice_regions = self.results.get('voice_regions', {})
        if voice_regions:
            reachable_count = sum(1 for r in voice_regions.values() if r.get('connectivity', {}).get('reachable', False))
            total_count = len(voice_regions)
            
            if reachable_count == 0:
                recommendations.append("🚨 No Discord voice regions are reachable - check firewall/network configuration")
            elif reachable_count < total_count * 0.5:
                recommendations.append("⚠️  Less than 50% of voice regions reachable - potential network issues")
            
            # Check for high latency regions
            high_latency_regions = []
            for region_id, region in voice_regions.items():
                latency = region.get('connectivity', {}).get('latency_ms', 0)
                if latency > 200:  # > 200ms is high
                    high_latency_regions.append(f"{region['name']} ({latency}ms)")
            
            if high_latency_regions:
                recommendations.append(f"⚠️  High latency to regions: {', '.join(high_latency_regions)}")
        
        # Check bot token issues
        bot_info = self.results.get('bot_info', {})
        if 'error' in bot_info:
            if bot_info['error'] == 'Invalid token':
                recommendations.append("❌ Bot token is invalid or expired - check DISCORD_TOKEN")
            elif bot_info['error'] == 'No token provided':
                recommendations.append("⚠️  No Discord token provided - cannot verify bot permissions")
        
        # Check WebSocket connectivity
        websocket = self.results.get('connectivity', {}).get('websocket', {})
        if not websocket.get('success', False):
            recommendations.append("❌ Discord WebSocket connectivity failed - check network/proxy settings")
        
        # General 4006 recommendations
        recommendations.extend([
            "🔧 For 4006 errors: Implement exponential backoff for voice reconnections",
            "🔧 Consider using different voice regions as fallback options",
            "🔧 Ensure bot has proper voice permissions in target channels",
            "🔧 Set appropriate auto_disconnect_timeout (recommended: 300 seconds)",
            "🔧 Monitor voice connection state changes and implement health checks"
        ])
        
        self.results['recommendations'] = recommendations
        return recommendations
    
    async def run_full_diagnostics(self) -> Dict:
        """Run all diagnostic tests"""
        logger.info("Starting Discord voice connection diagnostics...")
        
        # Run all diagnostic tests
        await self.check_discord_api_status()
        await self.test_voice_regions()
        await self.check_bot_info()
        await self.test_websocket_connectivity()
        
        # Generate recommendations
        self.generate_recommendations()
        
        logger.info("Diagnostics completed")
        return self.results
    
    def print_summary(self):
        """Print a summary of diagnostic results"""
        print("\n" + "="*60)
        print("DISCORD 4006 VOICE DIAGNOSTICS SUMMARY")
        print("="*60)
        
        # Discord status
        discord_status = self.results.get('discord_status', {})
        if discord_status.get('status', {}).get('success', False):
            status_desc = discord_status['status']['data'].get('status', {}).get('description', 'Unknown')
            print(f"✅ Discord Status: {status_desc}")
        else:
            print("❌ Discord Status: Check failed")
        
        # Voice regions
        voice_regions = self.results.get('voice_regions', {})
        if voice_regions:
            reachable = sum(1 for r in voice_regions.values() if r.get('connectivity', {}).get('reachable', False))
            total = len(voice_regions)
            print(f"🌐 Voice Regions: {reachable}/{total} reachable")
        
        # Bot info
        bot_info = self.results.get('bot_info', {})
        if 'user' in bot_info:
            username = bot_info['user'].get('username', 'Unknown')
            guild_count = bot_info.get('guilds', {}).get('count', 0)
            print(f"🤖 Bot: {username} (in {guild_count} guilds)")
        elif 'error' in bot_info:
            print(f"❌ Bot Info: {bot_info['error']}")
        
        # WebSocket connectivity
        websocket = self.results.get('connectivity', {}).get('websocket', {})
        if websocket.get('success', False):
            print("✅ WebSocket: Connected successfully")
        else:
            print("❌ WebSocket: Connection failed")
        
        # Recommendations
        recommendations = self.results.get('recommendations', [])
        if recommendations:
            print(f"\n📋 RECOMMENDATIONS ({len(recommendations)}):")
            for i, rec in enumerate(recommendations[:10], 1):  # Show first 10
                print(f"  {i}. {rec}")
            
            if len(recommendations) > 10:
                print(f"  ... and {len(recommendations) - 10} more (see full report)")
        
        print("="*60)

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Discord Voice Connection Diagnostics')
    parser.add_argument('--token', help='Discord bot token (can also use DISCORD_TOKEN env var)')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress summary output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get token
    token = args.token or os.getenv('DISCORD_TOKEN')
    
    async with DiscordVoiceDiagnostics(token) as diagnostics:
        results = await diagnostics.run_full_diagnostics()
        
        # Save results to file if specified
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
        # Print summary unless quiet mode
        if not args.quiet:
            diagnostics.print_summary()
        
        # Return appropriate exit code
        critical_failures = 0
        
        # Check for critical failures
        if not results.get('discord_status', {}).get('status', {}).get('success', False):
            critical_failures += 1
        
        voice_regions = results.get('voice_regions', {})
        if voice_regions:
            reachable = sum(1 for r in voice_regions.values() if r.get('connectivity', {}).get('reachable', False))
            if reachable == 0:
                critical_failures += 1
        
        if critical_failures > 0:
            logger.error(f"Diagnostics completed with {critical_failures} critical failures")
            sys.exit(1)
        else:
            logger.info("Diagnostics completed successfully")
            sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())