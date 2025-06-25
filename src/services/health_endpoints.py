"""
Health check endpoints for monitoring cookie health, platform status, and fallback systems.
Provides REST API endpoints for external health monitoring and debugging.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from aiohttp import web

logger = logging.getLogger(__name__)


class HealthEndpoints:
    """HTTP server for exposing health check endpoints"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8081):
        self.host = host
        self.port = port
        self.app = web.Application(middlewares=[self._cors_middleware])
        self.runner = None
        self.site = None
        
        # Service dependencies - will be set by main.py
        self.cookie_health_monitor = None
        self.fallback_manager = None  
        self.cookie_manager = None
        self.platform_registry = None
        self.quota_monitor = None
        
        self._setup_routes()
    
    def set_services(self, cookie_health_monitor=None, fallback_manager=None, 
                    cookie_manager=None, platform_registry=None, quota_monitor=None):
        """Set service dependencies"""
        self.cookie_health_monitor = cookie_health_monitor
        self.fallback_manager = fallback_manager
        self.cookie_manager = cookie_manager
        self.platform_registry = platform_registry
        self.quota_monitor = quota_monitor
    
    def _setup_routes(self):
        """Setup HTTP routes"""
        # Basic health check
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/health/detailed', self.detailed_health)
        
        # Cookie health endpoints
        self.app.router.add_get('/health/cookies', self.cookie_health)
        self.app.router.add_get('/health/cookies/{platform}', self.platform_cookie_health)
        self.app.router.add_post('/health/cookies/{platform}/refresh', self.refresh_platform_cookies)
        self.app.router.add_post('/health/cookies/validate', self.force_validation)
        
        # Platform and fallback status
        self.app.router.add_get('/health/platforms', self.platform_status)
        self.app.router.add_get('/health/fallback', self.fallback_status)
        
        # Quota monitoring endpoint
        self.app.router.add_get('/health/quota/youtube', self.youtube_quota_status)
    
    async def start(self):
        """Start the health check web server"""
        logger.info(f"Starting health endpoints on {self.host}:{self.port}")
        
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"Health endpoints running at http://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to start health endpoints: {e}")
            raise
    
    async def stop(self):
        """Stop the health check web server"""
        logger.info("Stopping health endpoints")
        
        if self.site:
            await self.site.stop()
        
        if self.runner:
            await self.runner.cleanup()
    
    @web.middleware
    async def _cors_middleware(self, request, handler):
        """Add CORS headers for cross-origin requests"""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    async def health_check(self, request):
        """Basic health check endpoint"""
        try:
            status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0',
                'services': {
                    'cookie_health_monitor': bool(self.cookie_health_monitor),
                    'fallback_manager': bool(self.fallback_manager),
                    'cookie_manager': bool(self.cookie_manager),
                    'platform_registry': bool(self.platform_registry),
                    'quota_monitor': bool(self.quota_monitor)
                }
            }
            
            return web.json_response(status)
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return web.json_response(
                {'status': 'error', 'error': str(e)},
                status=500
            )
    
    async def cookie_health(self, request):
        """Cookie health status for all platforms"""
        try:
            if not self.cookie_health_monitor:
                return web.json_response(
                    {'error': 'Cookie health monitor not available'},
                    status=503
                )
            
            health_report = await self.cookie_health_monitor.get_health_report()
            return web.json_response(health_report)
            
        except Exception as e:
            logger.error(f"Cookie health check error: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )
    
    async def platform_cookie_health(self, request):
        """Cookie health status for a specific platform"""
        platform = request.match_info['platform']
        
        try:
            if not self.cookie_health_monitor:
                return web.json_response(
                    {'error': 'Cookie health monitor not available'},
                    status=503
                )
            
            status = self.cookie_health_monitor.get_platform_status(platform)
            if not status:
                return web.json_response(
                    {'error': f'Platform {platform} not found'},
                    status=404
                )
            
            return web.json_response({
                'platform': platform,
                'status': status.to_dict(),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Platform cookie health error for {platform}: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )
    
    async def fallback_status(self, request):
        """Fallback system status"""
        try:
            if not self.fallback_manager:
                return web.json_response(
                    {'error': 'Fallback manager not available'},
                    status=503
                )
            
            report = self.fallback_manager.get_fallback_report()
            return web.json_response(report)
            
        except Exception as e:
            logger.error(f"Fallback status error: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )
    
    async def platform_status(self, request):
        """Overall platform status"""
        try:
            if not self.platform_registry:
                return web.json_response(
                    {'error': 'Platform registry not available'},
                    status=503
                )
            
            platforms = {}
            
            for platform_name in ['youtube', 'rumble', 'odysee', 'peertube']:
                platform_info = {
                    'available': False,
                    'healthy': False,
                    'in_fallback': False,
                    'fallback_mode': None,
                    'cookie_status': None
                }
                
                # Check if platform is registered
                try:
                    platform = self.platform_registry.get_platform(platform_name)
                    platform_info['available'] = bool(platform)
                except Exception:
                    platform_info['available'] = False
                
                # Check cookie health
                if self.cookie_health_monitor:
                    platform_info['healthy'] = self.cookie_health_monitor.is_platform_healthy(platform_name)
                    status = self.cookie_health_monitor.get_platform_status(platform_name)
                    if status:
                        platform_info['cookie_status'] = {
                            'count': status.cookie_count,
                            'age_hours': status.age_hours,
                            'error': status.validation_error
                        }
                
                # Check fallback status
                if self.fallback_manager:
                    platform_info['in_fallback'] = self.fallback_manager.is_platform_in_fallback(platform_name)
                    platform_info['fallback_mode'] = (
                        self.fallback_manager.get_platform_fallback_mode(platform_name).value
                        if platform_info['in_fallback'] else None
                    )
                
                platforms[platform_name] = platform_info
            
            return web.json_response({
                'timestamp': datetime.now().isoformat(),
                'platforms': platforms
            })
            
        except Exception as e:
            logger.error(f"Platform status error: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )
    
    async def detailed_health(self, request):
        """Comprehensive health report"""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'healthy',
                'issues': []
            }
            
            # Cookie health
            if self.cookie_health_monitor:
                cookie_report = await self.cookie_health_monitor.get_health_report()
                report['cookie_health'] = cookie_report
                
                unhealthy_platforms = cookie_report['overall_health']['unhealthy_platforms']
                if unhealthy_platforms:
                    report['issues'].extend([
                        f"Cookie issues on {platform}" for platform in unhealthy_platforms
                    ])
            else:
                report['issues'].append('Cookie health monitor not available')
            
            # Fallback status
            if self.fallback_manager:
                fallback_report = self.fallback_manager.get_fallback_report()
                report['fallback_status'] = fallback_report
                
                active_fallbacks = fallback_report['summary']['active_fallbacks']
                if active_fallbacks > 0:
                    report['issues'].append(f"{active_fallbacks} platforms in fallback mode")
            else:
                report['issues'].append('Fallback manager not available')
            
            # Platform registry
            if self.platform_registry:
                try:
                    platform_count = len(self.platform_registry.platforms)
                    report['platform_registry'] = {
                        'available': True,
                        'platform_count': platform_count
                    }
                except Exception as e:
                    report['issues'].append(f"Platform registry error: {e}")
            else:
                report['issues'].append('Platform registry not available')
            
            # Set overall status
            if report['issues']:
                report['overall_status'] = 'degraded' if len(report['issues']) < 3 else 'unhealthy'
            
            return web.json_response(report)
            
        except Exception as e:
            logger.error(f"Detailed health check error: {e}")
            return web.json_response(
                {
                    'timestamp': datetime.now().isoformat(),
                    'overall_status': 'error',
                    'error': str(e)
                },
                status=500
            )
    
    async def refresh_platform_cookies(self, request):
        """Force refresh cookies for a specific platform"""
        platform = request.match_info['platform']
        
        try:
            if not self.cookie_manager:
                return web.json_response(
                    {'error': 'Cookie manager not available'},
                    status=503
                )
            
            logger.info(f"Manual cookie refresh requested for {platform}")
            
            # Force refresh for the specific platform
            if hasattr(self.cookie_manager, 'refresh_cookies'):
                if hasattr(self.cookie_manager, 'extract_browser_cookies'):
                    # Single platform refresh
                    success = await self.cookie_manager.extract_browser_cookies(platform)
                    
                    return web.json_response({
                        'platform': platform,
                        'success': success,
                        'timestamp': datetime.now().isoformat(),
                        'message': f"Cookie refresh {'successful' if success else 'failed'} for {platform}"
                    })
                else:
                    return web.json_response(
                        {'error': 'Cookie refresh not supported by this manager'},
                        status=501
                    )
            else:
                return web.json_response(
                    {'error': 'Cookie refresh not available'},
                    status=501
                )
                
        except Exception as e:
            logger.error(f"Cookie refresh error for {platform}: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )
    
    async def force_validation(self, request):
        """Force validation of all cookies"""
        try:
            if not self.cookie_health_monitor:
                return web.json_response(
                    {'error': 'Cookie health monitor not available'},
                    status=503
                )
            
            logger.info("Manual cookie validation requested")
            
            # Force health check
            results = await self.cookie_health_monitor.force_health_check()
            
            return web.json_response({
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'platforms_checked': len(results),
                'results': {
                    platform: status.to_dict()
                    for platform, status in results.items()
                }
            })
            
        except Exception as e:
            logger.error(f"Force validation error: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )
    
    async def youtube_quota_status(self, request):
        """Get YouTube API quota status"""
        try:
            if not self.quota_monitor:
                return web.json_response(
                    {'error': 'Quota monitor not available'},
                    status=503
                )
            
            # Get comprehensive quota status
            quota_status = self.quota_monitor.get_quota_status()
            
            # Add conservation recommendations
            recommendations = self.quota_monitor.get_conservation_recommendations()
            quota_status['conservation'] = recommendations
            
            # Add health indicator
            if quota_status['percentage_remaining'] > 50:
                quota_status['health'] = 'healthy'
            elif quota_status['percentage_remaining'] > 20:
                quota_status['health'] = 'caution'
            elif quota_status['percentage_remaining'] > 10:
                quota_status['health'] = 'critical'
            else:
                quota_status['health'] = 'exhausted'
            
            return web.json_response(quota_status)
            
        except Exception as e:
            logger.error(f"YouTube quota status error: {e}")
            return web.json_response(
                {'error': str(e)},
                status=500
            )