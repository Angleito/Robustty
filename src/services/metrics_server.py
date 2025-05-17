"""
HTTP server for exposing Prometheus metrics.
"""

import asyncio
from aiohttp import web
from .metrics_collector import get_metrics_collector


class MetricsServer:
    """Simple HTTP server for exposing metrics endpoint."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_get('/metrics', self.handle_metrics)
        self.app.router.add_get('/health', self.handle_health)
        
    async def handle_metrics(self, request):
        """Handle metrics endpoint request."""
        collector = get_metrics_collector()
        metrics_data = collector.get_metrics()
        return web.Response(
            body=metrics_data,
            content_type='text/plain; version=0.0.4'
        )
        
    async def handle_health(self, request):
        """Handle health check endpoint."""
        return web.json_response({'status': 'healthy'})
        
    async def start(self):
        """Start the metrics server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        print(f"Metrics server started on http://{self.host}:{self.port}")
        
    async def stop(self):
        """Stop the metrics server."""
        if self.runner:
            await self.runner.cleanup()
            
    async def run_forever(self):
        """Run the server forever."""
        await self.start()
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            await self.stop()