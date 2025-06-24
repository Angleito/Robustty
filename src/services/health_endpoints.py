"""Health check endpoints for monitoring cookie and platform status

This module provides HTTP endpoints for monitoring the health of cookies,
platforms, and fallback systems in VPS deployments.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from aiohttp import web, ClientTimeout
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class HealthEndpoints:
    """HTTP endpoints for health checking and monitoring"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.cookie_health_monitor = None
        self.fallback_manager = None
        self.cookie_manager = None
        self.platform_registry = None
        
        # Configuration
        self.enabled = config.get('health_endpoints', {}).get('enabled', True)
        self.port = config.get('health_endpoints', {}).get('port', 8080)
        self.host = config.get('health_endpoints', {}).get('host', '0.0.0.0')
        
        # Server
        self.app = None
        self.runner = None
        self.site = None
        
    def set_dependencies(self, cookie_health_monitor, fallback_manager, cookie_manager, platform_registry):
        """Set service dependencies"""
        self.cookie_health_monitor = cookie_health_monitor
        self.fallback_manager = fallback_manager
        self.cookie_manager = cookie_manager
        self.platform_registry = platform_registry
    
    async def start(self):
        """Start the health check web server"""
        if not self.enabled:
            logger.info("Health endpoints are disabled")
            return
        
        logger.info(f"Starting health endpoints on {self.host}:{self.port}")
        
        # Create web application
        self.app = web.Application()
        
        # Add routes
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/health/cookies', self.cookie_health)
        self.app.router.add_get('/health/cookies/{platform}', self.platform_cookie_health)
        self.app.router.add_get('/health/fallbacks', self.fallback_status)
        self.app.router.add_get('/health/platforms', self.platform_status)
        self.app.router.add_get('/health/detailed', self.detailed_health)
        self.app.router.add_post('/health/refresh/{platform}', self.refresh_platform_cookies)
        self.app.router.add_post('/health/validate', self.force_validation)
        
        # Add CORS headers for external monitoring
        self.app.middlewares.append(self._cors_middleware)
        
        # Start server
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"Health endpoints running at http://{self.host}:{self.port}")
            
        except Exception as e:\n            logger.error(f\"Failed to start health endpoints: {e}\")\n            raise\n    \n    async def stop(self):\n        \"\"\"Stop the health check web server\"\"\"\n        logger.info(\"Stopping health endpoints\")\n        \n        if self.site:\n            await self.site.stop()\n        \n        if self.runner:\n            await self.runner.cleanup()\n    \n    @web.middleware\n    async def _cors_middleware(self, request, handler):\n        \"\"\"Add CORS headers for cross-origin requests\"\"\"\n        response = await handler(request)\n        response.headers['Access-Control-Allow-Origin'] = '*'\n        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'\n        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'\n        return response\n    \n    async def health_check(self, request):\n        \"\"\"Basic health check endpoint\"\"\"\n        try:\n            status = {\n                'status': 'healthy',\n                'timestamp': datetime.now().isoformat(),\n                'version': '1.0.0',\n                'services': {\n                    'cookie_health_monitor': bool(self.cookie_health_monitor),\n                    'fallback_manager': bool(self.fallback_manager),\n                    'cookie_manager': bool(self.cookie_manager),\n                    'platform_registry': bool(self.platform_registry)\n                }\n            }\n            \n            return web.json_response(status)\n            \n        except Exception as e:\n            logger.error(f\"Health check error: {e}\")\n            return web.json_response(\n                {'status': 'error', 'error': str(e)},\n                status=500\n            )\n    \n    async def cookie_health(self, request):\n        \"\"\"Cookie health status for all platforms\"\"\"\n        try:\n            if not self.cookie_health_monitor:\n                return web.json_response(\n                    {'error': 'Cookie health monitor not available'},\n                    status=503\n                )\n            \n            health_report = await self.cookie_health_monitor.get_health_report()\n            return web.json_response(health_report)\n            \n        except Exception as e:\n            logger.error(f\"Cookie health check error: {e}\")\n            return web.json_response(\n                {'error': str(e)},\n                status=500\n            )\n    \n    async def platform_cookie_health(self, request):\n        \"\"\"Cookie health status for a specific platform\"\"\"\n        platform = request.match_info['platform']\n        \n        try:\n            if not self.cookie_health_monitor:\n                return web.json_response(\n                    {'error': 'Cookie health monitor not available'},\n                    status=503\n                )\n            \n            status = self.cookie_health_monitor.get_platform_status(platform)\n            if not status:\n                return web.json_response(\n                    {'error': f'Platform {platform} not found'},\n                    status=404\n                )\n            \n            return web.json_response({\n                'platform': platform,\n                'status': status.to_dict(),\n                'timestamp': datetime.now().isoformat()\n            })\n            \n        except Exception as e:\n            logger.error(f\"Platform cookie health error for {platform}: {e}\")\n            return web.json_response(\n                {'error': str(e)},\n                status=500\n            )\n    \n    async def fallback_status(self, request):\n        \"\"\"Fallback system status\"\"\"\n        try:\n            if not self.fallback_manager:\n                return web.json_response(\n                    {'error': 'Fallback manager not available'},\n                    status=503\n                )\n            \n            report = self.fallback_manager.get_fallback_report()\n            return web.json_response(report)\n            \n        except Exception as e:\n            logger.error(f\"Fallback status error: {e}\")\n            return web.json_response(\n                {'error': str(e)},\n                status=500\n            )\n    \n    async def platform_status(self, request):\n        \"\"\"Overall platform status\"\"\"\n        try:\n            if not self.platform_registry:\n                return web.json_response(\n                    {'error': 'Platform registry not available'},\n                    status=503\n                )\n            \n            platforms = {}\n            \n            for platform_name in ['youtube', 'rumble', 'odysee', 'peertube']:\n                platform_info = {\n                    'available': False,\n                    'healthy': False,\n                    'in_fallback': False,\n                    'fallback_mode': None,\n                    'cookie_status': None\n                }\n                \n                # Check if platform is registered\n                try:\n                    platform = self.platform_registry.get_platform(platform_name)\n                    platform_info['available'] = bool(platform)\n                except Exception:\n                    platform_info['available'] = False\n                \n                # Check cookie health\n                if self.cookie_health_monitor:\n                    platform_info['healthy'] = self.cookie_health_monitor.is_platform_healthy(platform_name)\n                    status = self.cookie_health_monitor.get_platform_status(platform_name)\n                    if status:\n                        platform_info['cookie_status'] = {\n                            'count': status.cookie_count,\n                            'age_hours': status.age_hours,\n                            'error': status.validation_error\n                        }\n                \n                # Check fallback status\n                if self.fallback_manager:\n                    platform_info['in_fallback'] = self.fallback_manager.is_platform_in_fallback(platform_name)\n                    platform_info['fallback_mode'] = (\n                        self.fallback_manager.get_platform_fallback_mode(platform_name).value\n                        if platform_info['in_fallback'] else None\n                    )\n                \n                platforms[platform_name] = platform_info\n            \n            return web.json_response({\n                'timestamp': datetime.now().isoformat(),\n                'platforms': platforms\n            })\n            \n        except Exception as e:\n            logger.error(f\"Platform status error: {e}\")\n            return web.json_response(\n                {'error': str(e)},\n                status=500\n            )\n    \n    async def detailed_health(self, request):\n        \"\"\"Comprehensive health report\"\"\"\n        try:\n            report = {\n                'timestamp': datetime.now().isoformat(),\n                'overall_status': 'healthy',\n                'issues': []\n            }\n            \n            # Cookie health\n            if self.cookie_health_monitor:\n                cookie_report = await self.cookie_health_monitor.get_health_report()\n                report['cookie_health'] = cookie_report\n                \n                unhealthy_platforms = cookie_report['overall_health']['unhealthy_platforms']\n                if unhealthy_platforms:\n                    report['issues'].extend([\n                        f\"Cookie issues on {platform}\" for platform in unhealthy_platforms\n                    ])\n            else:\n                report['issues'].append('Cookie health monitor not available')\n            \n            # Fallback status\n            if self.fallback_manager:\n                fallback_report = self.fallback_manager.get_fallback_report()\n                report['fallback_status'] = fallback_report\n                \n                active_fallbacks = fallback_report['summary']['active_fallbacks']\n                if active_fallbacks > 0:\n                    report['issues'].append(f\"{active_fallbacks} platforms in fallback mode\")\n            else:\n                report['issues'].append('Fallback manager not available')\n            \n            # Platform registry\n            if self.platform_registry:\n                try:\n                    platform_count = len(self.platform_registry.platforms)\n                    report['platform_registry'] = {\n                        'available': True,\n                        'platform_count': platform_count\n                    }\n                except Exception as e:\n                    report['issues'].append(f\"Platform registry error: {e}\")\n            else:\n                report['issues'].append('Platform registry not available')\n            \n            # Set overall status\n            if report['issues']:\n                report['overall_status'] = 'degraded' if len(report['issues']) < 3 else 'unhealthy'\n            \n            return web.json_response(report)\n            \n        except Exception as e:\n            logger.error(f\"Detailed health check error: {e}\")\n            return web.json_response(\n                {\n                    'timestamp': datetime.now().isoformat(),\n                    'overall_status': 'error',\n                    'error': str(e)\n                },\n                status=500\n            )\n    \n    async def refresh_platform_cookies(self, request):\n        \"\"\"Force refresh cookies for a specific platform\"\"\"\n        platform = request.match_info['platform']\n        \n        try:\n            if not self.cookie_manager:\n                return web.json_response(\n                    {'error': 'Cookie manager not available'},\n                    status=503\n                )\n            \n            logger.info(f\"Manual cookie refresh requested for {platform}\")\n            \n            # Force refresh for the specific platform\n            if hasattr(self.cookie_manager, 'refresh_cookies'):\n                if hasattr(self.cookie_manager, 'extract_browser_cookies'):\n                    # Single platform refresh\n                    success = await self.cookie_manager.extract_browser_cookies(platform)\n                    \n                    return web.json_response({\n                        'platform': platform,\n                        'success': success,\n                        'timestamp': datetime.now().isoformat(),\n                        'message': f\"Cookie refresh {'successful' if success else 'failed'} for {platform}\"\n                    })\n                else:\n                    return web.json_response(\n                        {'error': 'Cookie refresh not supported by this manager'},\n                        status=501\n                    )\n            else:\n                return web.json_response(\n                    {'error': 'Cookie refresh not available'},\n                    status=501\n                )\n                \n        except Exception as e:\n            logger.error(f\"Cookie refresh error for {platform}: {e}\")\n            return web.json_response(\n                {'error': str(e)},\n                status=500\n            )\n    \n    async def force_validation(self, request):\n        \"\"\"Force validation of all cookies\"\"\"\n        try:\n            if not self.cookie_health_monitor:\n                return web.json_response(\n                    {'error': 'Cookie health monitor not available'},\n                    status=503\n                )\n            \n            logger.info(\"Manual cookie validation requested\")\n            \n            # Force health check\n            results = await self.cookie_health_monitor.force_health_check()\n            \n            return web.json_response({\n                'success': True,\n                'timestamp': datetime.now().isoformat(),\n                'platforms_checked': len(results),\n                'results': {\n                    platform: status.to_dict()\n                    for platform, status in results.items()\n                }\n            })\n            \n        except Exception as e:\n            logger.error(f\"Force validation error: {e}\")\n            return web.json_response(\n                {'error': str(e)},\n                status=500\n            )