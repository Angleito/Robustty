"""
HTTP server for exposing Prometheus metrics and comprehensive health check endpoints.
Provides dependency-free health checks for VPS deployment monitoring and auto-recovery.
"""

import asyncio
import json
import time
import os
import sys
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from aiohttp import web
from .metrics_collector import get_metrics_collector


class EnhancedMetricsServer:
    """Enhanced HTTP server for exposing metrics and comprehensive health check endpoints."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.bot = None  # Will be set by main.py
        self.start_time = time.time()
        self.health_cache = {}  # Cache for health check results
        self.cache_ttl = 30  # Cache TTL in seconds
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes with comprehensive health endpoints."""
        # Prometheus metrics
        self.app.router.add_get("/metrics", self.handle_metrics)

        # Basic health checks (dependency-free)
        self.app.router.add_get("/health", self.handle_basic_health)
        self.app.router.add_get("/ready", self.handle_readiness_probe)
        self.app.router.add_get("/live", self.handle_liveness_probe)

        # Detailed health reporting
        self.app.router.add_get("/health/detailed", self.handle_detailed_health)
        self.app.router.add_get("/health/discord", self.handle_discord_health)
        self.app.router.add_get("/health/platforms", self.handle_platforms_health)
        self.app.router.add_get("/health/performance", self.handle_performance_health)
        self.app.router.add_get(
            "/health/infrastructure", self.handle_infrastructure_health
        )
        self.app.router.add_get("/health/security", self.handle_security_health)

        # System information endpoints
        self.app.router.add_get("/info/system", self.handle_system_info)
        self.app.router.add_get("/info/runtime", self.handle_runtime_info)

    async def handle_metrics(self, request):
        """Handle metrics endpoint request."""
        collector = get_metrics_collector()
        metrics_data = collector.get_metrics()
        return web.Response(body=metrics_data, content_type="text/plain; version=0.0.4")

    async def handle_basic_health(self, request):
        """Handle basic health check endpoint - dependency-free."""
        try:
            # Basic checks without external dependencies
            uptime = time.time() - self.start_time
            memory_info = self._get_memory_info()

            # Simple health status based on memory and uptime
            if memory_info["memory_percent"] > 90:
                status = "degraded"
                message = "High memory usage"
            elif uptime < 30:  # Still starting up
                status = "starting"
                message = "Service starting up"
            else:
                status = "healthy"
                message = "Service operational"

            return web.json_response(
                {
                    "status": status,
                    "message": message,
                    "uptime": uptime,
                    "timestamp": datetime.utcnow().isoformat(),
                    "memory_percent": memory_info["memory_percent"],
                }
            )
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "message": f"Health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_detailed_health(self, request):
        """Handle detailed health check endpoint with comprehensive component status."""
        try:
            # Check cache first
            cache_key = "detailed_health"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return web.json_response(cached_result)

            # Gather comprehensive health information
            health_data = {
                "overall_status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": time.time() - self.start_time,
                "components": {},
            }

            # Basic system health
            health_data["components"]["system"] = await self._check_system_health()

            # Discord health (if bot available)
            if self.bot:
                health_data["components"][
                    "discord"
                ] = await self._check_discord_health_detailed()
                health_data["components"][
                    "platforms"
                ] = await self._check_platforms_health_detailed()
                health_data["components"][
                    "infrastructure"
                ] = await self._check_infrastructure_health_detailed()

                # Use health monitor if available
                if hasattr(self.bot, "health_monitor") and self.bot.health_monitor:
                    monitor_status = self.bot.health_monitor.get_health_status()
                    health_data["components"]["health_monitor"] = monitor_status
            else:
                health_data["components"]["discord"] = {
                    "status": "unavailable",
                    "message": "Bot not initialized",
                }

            # Determine overall status based on components
            health_data["overall_status"] = self._determine_overall_status(
                health_data["components"]
            )

            # Cache the result
            self._cache_result(cache_key, health_data)

            return web.json_response(health_data)

        except Exception as e:
            return web.json_response(
                {
                    "overall_status": "error",
                    "error": f"Detailed health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def start(self):
        """Start the enhanced metrics and health check server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        print(
            f"Enhanced metrics and health server started on http://{self.host}:{self.port}"
        )
        print(f"Available endpoints:")
        print(f"  - http://{self.host}:{self.port}/health (basic health)")
        print(f"  - http://{self.host}:{self.port}/ready (readiness probe)")
        print(f"  - http://{self.host}:{self.port}/live (liveness probe)")
        print(
            f"  - http://{self.host}:{self.port}/health/detailed (comprehensive health)"
        )
        print(f"  - http://{self.host}:{self.port}/metrics (Prometheus metrics)")

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

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information without external dependencies."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            return {
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "memory_total": memory.total,
                "memory_used": memory.used,
            }
        except ImportError:
            # Fallback without psutil
            try:
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                mem_info = {}
                for line in lines:
                    key, value = line.split(":")
                    mem_info[key.strip()] = (
                        int(value.strip().split()[0]) * 1024
                    )  # Convert to bytes

                total = mem_info.get("MemTotal", 0)
                available = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
                used = total - available
                percent = (used / total * 100) if total > 0 else 0

                return {
                    "memory_percent": percent,
                    "memory_available": available,
                    "memory_total": total,
                    "memory_used": used,
                }
            except (FileNotFoundError, PermissionError):
                # Last resort fallback
                return {
                    "memory_percent": 0,
                    "memory_available": 0,
                    "memory_total": 0,
                    "memory_used": 0,
                    "note": "Memory information unavailable",
                }

    def _get_cached_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached health check result if still valid."""
        if key in self.health_cache:
            cached_time, result = self.health_cache[key]
            if time.time() - cached_time < self.cache_ttl:
                return result
        return None

    def _cache_result(self, key: str, result: Dict[str, Any]) -> None:
        """Cache health check result."""
        self.health_cache[key] = (time.time(), result)

    def _determine_overall_status(self, components: Dict[str, Any]) -> str:
        """Determine overall health status from component statuses."""
        statuses = []
        for component in components.values():
            if isinstance(component, dict):
                status = component.get("status", "unknown")
                if isinstance(status, str):
                    statuses.append(status)
                elif isinstance(status, dict) and "overall_status" in status:
                    statuses.append(status["overall_status"])

        # Priority: error > unhealthy > degraded > warning > starting > healthy
        if any(s in ["error", "unhealthy"] for s in statuses):
            return "unhealthy"
        elif any(s in ["degraded", "warning"] for s in statuses):
            return "degraded"
        elif any(s == "starting" for s in statuses):
            return "starting"
        elif any(s == "healthy" for s in statuses):
            return "healthy"
        else:
            return "unknown"

    async def _check_system_health(self) -> Dict[str, Any]:
        """Check basic system health."""
        try:
            memory_info = self._get_memory_info()

            # CPU usage check
            try:
                import psutil

                cpu_percent = psutil.cpu_percent(interval=1)
                load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
            except (ImportError, AttributeError):
                cpu_percent = 0
                load_avg = (0, 0, 0)

            # Disk usage check
            try:
                import shutil

                disk_usage = shutil.disk_usage("/")
                disk_percent = (
                    (disk_usage.used / disk_usage.total * 100)
                    if disk_usage.total > 0
                    else 0
                )
            except (ImportError, OSError):
                disk_percent = 0

            # Determine status
            if (
                memory_info["memory_percent"] > 90
                or cpu_percent > 90
                or disk_percent > 95
            ):
                status = "unhealthy"
                message = "Critical resource usage"
            elif (
                memory_info["memory_percent"] > 80
                or cpu_percent > 80
                or disk_percent > 85
            ):
                status = "degraded"
                message = "High resource usage"
            else:
                status = "healthy"
                message = "System resources normal"

            return {
                "status": status,
                "message": message,
                "metrics": {
                    "memory_percent": memory_info["memory_percent"],
                    "cpu_percent": cpu_percent,
                    "disk_percent": disk_percent,
                    "load_average": load_avg,
                    "uptime": time.time() - self.start_time,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"System health check failed: {str(e)}",
            }

    async def _check_discord_health_detailed(self) -> Dict[str, Any]:
        """Check Discord connectivity and functionality in detail."""
        try:
            if not self.bot:
                return {"status": "unavailable", "message": "Bot not initialized"}

            health_info = {
                "status": "healthy",
                "message": "Discord connection operational",
                "metrics": {},
            }

            # Basic connection status
            if not self.bot.is_ready():
                health_info["status"] = "unhealthy"
                health_info["message"] = "Bot not ready"
            elif self.bot.ws is None or self.bot.ws.socket is None:
                health_info["status"] = "unhealthy"
                health_info["message"] = "WebSocket not connected"
            else:
                # Check latency
                latency = self.bot.latency
                health_info["metrics"]["latency"] = latency

                if latency == float("inf"):
                    health_info["status"] = "unhealthy"
                    health_info["message"] = "Infinite latency"
                elif latency > 1.0:
                    health_info["status"] = "degraded"
                    health_info["message"] = f"High latency: {latency:.2f}s"

            # Additional metrics
            health_info["metrics"].update(
                {
                    "guild_count": len(self.bot.guilds),
                    "user_id": self.bot.user.id if self.bot.user else None,
                    "active_voice_connections": len(
                        [
                            p
                            for p in self.bot.audio_players.values()
                            if p.voice_client and p.voice_client.is_connected()
                        ]
                    ),
                    "total_players": len(self.bot.audio_players),
                }
            )

            return health_info
        except Exception as e:
            return {
                "status": "error",
                "message": f"Discord health check failed: {str(e)}",
            }

    async def _check_platforms_health_detailed(self) -> Dict[str, Any]:
        """Check platform API connectivity and cookie status."""
        try:
            if not self.bot or not hasattr(self.bot, "platform_registry"):
                return {
                    "status": "unavailable",
                    "message": "Platform registry not available",
                }

            platforms_health = {
                "status": "healthy",
                "message": "All platforms operational",
                "platforms": {},
            }

            enabled_platforms = self.bot.platform_registry.get_enabled_platforms()

            for platform_name, platform in enabled_platforms.items():
                try:
                    platform_health = {
                        "status": "healthy",
                        "enabled": platform.enabled,
                        "metrics": {},
                    }

                    # Cookie status check
                    if hasattr(self.bot, "cookie_manager") and self.bot.cookie_manager:
                        cookie_status = await self._check_platform_cookies(
                            platform_name
                        )
                        platform_health["cookies"] = cookie_status

                    platforms_health["platforms"][platform_name] = platform_health

                except Exception as platform_error:
                    platforms_health["platforms"][platform_name] = {
                        "status": "error",
                        "message": f"Platform check failed: {str(platform_error)}",
                    }
                    platforms_health["status"] = "degraded"

            return platforms_health
        except Exception as e:
            return {
                "status": "error",
                "message": f"Platform health check failed: {str(e)}",
            }

    async def _check_platform_cookies(self, platform_name: str) -> Dict[str, Any]:
        """Check cookie status for a specific platform."""
        try:
            cookie_manager = self.bot.cookie_manager
            cookie_paths = [
                f"/app/cookies/{platform_name}_cookies.txt",
                f"./cookies/{platform_name}_cookies.txt",
                f"data/cookies/{platform_name}_cookies.txt",
            ]

            for cookie_path in cookie_paths:
                if os.path.exists(cookie_path):
                    stat = os.stat(cookie_path)
                    age = time.time() - stat.st_mtime

                    # Consider cookies stale if older than 24 hours
                    if age > 86400:  # 24 hours
                        return {
                            "status": "stale",
                            "path": cookie_path,
                            "age_hours": age / 3600,
                            "message": "Cookies are stale",
                        }
                    else:
                        return {
                            "status": "fresh",
                            "path": cookie_path,
                            "age_hours": age / 3600,
                            "message": "Cookies are fresh",
                        }

            return {"status": "missing", "message": "No cookie files found"}
        except Exception as e:
            return {"status": "error", "message": f"Cookie check failed: {str(e)}"}

    async def _check_infrastructure_health_detailed(self) -> Dict[str, Any]:
        """Check infrastructure components (Redis, filesystem, etc.)."""
        try:
            infra_health = {
                "status": "healthy",
                "message": "Infrastructure operational",
                "components": {},
            }

            # Redis health
            if hasattr(self.bot, "cache_manager") and self.bot.cache_manager:
                redis_health = await self._check_redis_health()
                infra_health["components"]["redis"] = redis_health
                if redis_health["status"] in ["unhealthy", "error"]:
                    infra_health["status"] = "degraded"

            # Filesystem health
            fs_health = self._check_filesystem_health()
            infra_health["components"]["filesystem"] = fs_health
            if fs_health["status"] in ["unhealthy", "error"]:
                infra_health["status"] = "degraded"

            return infra_health
        except Exception as e:
            return {
                "status": "error",
                "message": f"Infrastructure health check failed: {str(e)}",
            }

    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance."""
        try:
            cache_manager = self.bot.cache_manager
            if not cache_manager or not cache_manager.redis_client:
                return {"status": "unavailable", "message": "Redis not configured"}

            # Test Redis with ping
            start_time = time.time()
            test_key = "health_check_test"
            await cache_manager.redis_client.set(test_key, "ping", ex=10)
            result = await cache_manager.redis_client.get(test_key)
            response_time = time.time() - start_time

            if result != "ping":
                return {
                    "status": "unhealthy",
                    "message": "Redis ping test failed",
                    "response_time": response_time,
                }

            # Clean up test key
            await cache_manager.redis_client.delete(test_key)

            # Check response time
            if response_time > 1.0:
                status = "degraded"
                message = f"Slow Redis response: {response_time:.2f}s"
            else:
                status = "healthy"
                message = "Redis operational"

            return {
                "status": status,
                "message": message,
                "response_time": response_time,
                "ping_success": True,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Redis health check failed: {str(e)}",
            }

    def _check_filesystem_health(self) -> Dict[str, Any]:
        """Check filesystem health and permissions."""
        try:
            health_info = {
                "status": "healthy",
                "message": "Filesystem operational",
                "checks": {},
            }

            # Check critical directories
            critical_dirs = [
                "/app/logs",
                "/app/data",
                "/app/cookies",
                "./logs",
                "./data",
                "./cookies",
            ]
            for dir_path in critical_dirs:
                if os.path.exists(dir_path):
                    readable = os.access(dir_path, os.R_OK)
                    writable = os.access(dir_path, os.W_OK)
                    health_info["checks"][dir_path] = {
                        "exists": True,
                        "readable": readable,
                        "writable": writable,
                        "status": "healthy" if readable and writable else "degraded",
                    }

                    if not readable or not writable:
                        health_info["status"] = "degraded"
                        health_info["message"] = (
                            "Some directories have permission issues"
                        )
                else:
                    health_info["checks"][dir_path] = {
                        "exists": False,
                        "status": "missing",
                    }

            return health_info
        except Exception as e:
            return {"status": "error", "message": f"Filesystem check failed: {str(e)}"}

    async def handle_readiness_probe(self, request):
        """Kubernetes-style readiness probe - checks if service is ready to receive traffic."""
        try:
            # Service is ready if:
            # 1. Bot is initialized and ready
            # 2. Key services are operational
            # 3. No critical errors

            ready = True
            checks = {}

            # Bot readiness
            if not self.bot:
                ready = False
                checks["bot"] = {"ready": False, "reason": "Bot not initialized"}
            elif not self.bot.is_ready():
                ready = False
                checks["bot"] = {"ready": False, "reason": "Bot not ready"}
            else:
                checks["bot"] = {"ready": True}

            # Memory check
            memory_info = self._get_memory_info()
            if memory_info["memory_percent"] > 95:
                ready = False
                checks["memory"] = {"ready": False, "reason": "Critical memory usage"}
            else:
                checks["memory"] = {
                    "ready": True,
                    "usage_percent": memory_info["memory_percent"],
                }

            # Platform registry check
            if self.bot and hasattr(self.bot, "platform_registry"):
                enabled_count = len(self.bot.platform_registry.get_enabled_platforms())
                if enabled_count == 0:
                    ready = False
                    checks["platforms"] = {
                        "ready": False,
                        "reason": "No platforms enabled",
                    }
                else:
                    checks["platforms"] = {
                        "ready": True,
                        "enabled_count": enabled_count,
                    }

            status_code = 200 if ready else 503
            return web.json_response(
                {
                    "ready": ready,
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": checks,
                },
                status=status_code,
            )

        except Exception as e:
            return web.json_response(
                {
                    "ready": False,
                    "error": f"Readiness check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_liveness_probe(self, request):
        """Kubernetes-style liveness probe - checks if service is alive and should not be restarted."""
        try:
            # Service is alive if:
            # 1. Process is running (obviously true if we can respond)
            # 2. Memory usage is not critically high
            # 3. No deadlocks or hanging processes

            alive = True
            checks = {}

            # Process uptime
            uptime = time.time() - self.start_time
            checks["uptime"] = {
                "seconds": uptime,
                "healthy": uptime > 10,
            }  # At least 10 seconds

            # Memory check (more lenient than readiness)
            memory_info = self._get_memory_info()
            if memory_info["memory_percent"] > 98:
                alive = False
                checks["memory"] = {"alive": False, "reason": "Memory exhausted"}
            else:
                checks["memory"] = {
                    "alive": True,
                    "usage_percent": memory_info["memory_percent"],
                }

            # Thread/async task health (basic check)
            try:
                current_task = asyncio.current_task()
                checks["async"] = {
                    "alive": True,
                    "current_task": str(current_task) if current_task else None,
                }
            except Exception:
                checks["async"] = {"alive": True, "note": "Async check unavailable"}

            status_code = 200 if alive else 503
            return web.json_response(
                {
                    "alive": alive,
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": checks,
                },
                status=status_code,
            )

        except Exception as e:
            return web.json_response(
                {
                    "alive": False,
                    "error": f"Liveness check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_discord_health(self, request):
        """Discord-specific health endpoint."""
        try:
            cache_key = "discord_health"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return web.json_response(cached_result)

            discord_health = await self._check_discord_health_detailed()
            self._cache_result(cache_key, discord_health)

            return web.json_response(discord_health)
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "message": f"Discord health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_platforms_health(self, request):
        """Platform-specific health endpoint."""
        try:
            cache_key = "platforms_health"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return web.json_response(cached_result)

            platforms_health = await self._check_platforms_health_detailed()
            self._cache_result(cache_key, platforms_health)

            return web.json_response(platforms_health)
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "message": f"Platform health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_performance_health(self, request):
        """Performance metrics and thresholds health endpoint."""
        try:
            cache_key = "performance_health"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return web.json_response(cached_result)

            perf_health = {
                "status": "healthy",
                "message": "Performance within thresholds",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {},
            }

            # System performance
            system_health = await self._check_system_health()
            perf_health["metrics"]["system"] = system_health["metrics"]

            # Discord performance
            if self.bot and self.bot.is_ready():
                latency = self.bot.latency
                perf_health["metrics"]["discord"] = {
                    "latency": latency,
                    "latency_status": (
                        "healthy"
                        if latency < 0.5
                        else "degraded" if latency < 1.0 else "unhealthy"
                    ),
                }

                # Voice connection performance
                voice_metrics = {
                    "active_connections": len(
                        [
                            p
                            for p in self.bot.audio_players.values()
                            if p.voice_client and p.voice_client.is_connected()
                        ]
                    ),
                    "total_players": len(self.bot.audio_players),
                }
                perf_health["metrics"]["voice"] = voice_metrics

            # Determine overall performance status
            if system_health.get("status") == "unhealthy" or (
                self.bot and self.bot.latency > 2.0
            ):
                perf_health["status"] = "unhealthy"
                perf_health["message"] = "Performance degraded significantly"
            elif system_health.get("status") == "degraded" or (
                self.bot and self.bot.latency > 1.0
            ):
                perf_health["status"] = "degraded"
                perf_health["message"] = "Performance below optimal"

            self._cache_result(cache_key, perf_health)
            return web.json_response(perf_health)

        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "message": f"Performance health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_infrastructure_health(self, request):
        """Infrastructure health endpoint."""
        try:
            cache_key = "infrastructure_health"
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return web.json_response(cached_result)

            infra_health = await self._check_infrastructure_health_detailed()
            self._cache_result(cache_key, infra_health)

            return web.json_response(infra_health)
        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "message": f"Infrastructure health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_security_health(self, request):
        """Security health endpoint."""
        try:
            security_health = {
                "status": "healthy",
                "message": "Security checks passed",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {},
            }

            # File permissions check
            security_health["checks"][
                "file_permissions"
            ] = self._check_file_permissions()

            # Environment variables check
            security_health["checks"][
                "environment"
            ] = self._check_environment_security()

            # Process security check
            security_health["checks"]["process"] = self._check_process_security()

            # Determine overall security status
            checks = security_health["checks"]
            if any(check.get("status") == "critical" for check in checks.values()):
                security_health["status"] = "critical"
                security_health["message"] = "Critical security issues detected"
            elif any(check.get("status") == "warning" for check in checks.values()):
                security_health["status"] = "warning"
                security_health["message"] = "Security warnings detected"

            return web.json_response(security_health)

        except Exception as e:
            return web.json_response(
                {
                    "status": "error",
                    "message": f"Security health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    def _check_file_permissions(self) -> Dict[str, Any]:
        """Check file and directory permissions for security issues."""
        try:
            perm_check = {
                "status": "healthy",
                "message": "File permissions secure",
                "issues": [],
            }

            # Check sensitive directories
            sensitive_dirs = ["/app/cookies", "./cookies", "/app/data", "./data"]
            for dir_path in sensitive_dirs:
                if os.path.exists(dir_path):
                    stat_info = os.stat(dir_path)
                    mode = stat_info.st_mode

                    # Check if directory is world-readable or world-writable
                    if mode & 0o044:  # World readable
                        perm_check["issues"].append(f"{dir_path} is world-readable")
                        perm_check["status"] = "warning"
                    if mode & 0o022:  # World writable
                        perm_check["issues"].append(f"{dir_path} is world-writable")
                        perm_check["status"] = "critical"

            if perm_check["issues"]:
                perm_check["message"] = (
                    f"Found {len(perm_check['issues'])} permission issues"
                )

            return perm_check
        except Exception as e:
            return {"status": "error", "message": f"Permission check failed: {str(e)}"}

    def _check_environment_security(self) -> Dict[str, Any]:
        """Check environment variables for security issues."""
        try:
            env_check = {
                "status": "healthy",
                "message": "Environment variables secure",
                "issues": [],
            }

            # Check for required sensitive variables
            required_vars = ["DISCORD_TOKEN", "YOUTUBE_API_KEY"]
            for var in required_vars:
                if not os.getenv(var):
                    env_check["issues"].append(
                        f"Missing required environment variable: {var}"
                    )
                    env_check["status"] = "critical"
                elif len(os.getenv(var, "")) < 10:  # Basic sanity check
                    env_check["issues"].append(
                        f"Environment variable {var} appears to be invalid"
                    )
                    env_check["status"] = "warning"

            if env_check["issues"]:
                env_check["message"] = (
                    f"Found {len(env_check['issues'])} environment issues"
                )

            return env_check
        except Exception as e:
            return {"status": "error", "message": f"Environment check failed: {str(e)}"}

    def _check_process_security(self) -> Dict[str, Any]:
        """Check process security settings."""
        try:
            process_check = {
                "status": "healthy",
                "message": "Process security normal",
                "info": {},
            }

            # Check if running as root (security risk)
            try:
                uid = os.getuid()
                process_check["info"]["uid"] = uid
                if uid == 0:
                    process_check["status"] = "warning"
                    process_check["message"] = "Running as root user (security risk)"
            except AttributeError:
                # Windows doesn't have getuid
                pass

            # Check process limits
            try:
                import resource

                nofile_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                process_check["info"]["file_descriptor_limit"] = nofile_limit
                if nofile_limit[0] < 1024:  # Soft limit
                    process_check["status"] = "warning"
                    process_check["message"] = "Low file descriptor limit"
            except (ImportError, OSError):
                pass

            return process_check
        except Exception as e:
            return {
                "status": "error",
                "message": f"Process security check failed: {str(e)}",
            }

    async def handle_system_info(self, request):
        """System information endpoint."""
        try:
            system_info = {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": time.time() - self.start_time,
                "system": {},
                "python": {},
                "bot": {},
            }

            # System information
            system_info["system"] = {
                "platform": sys.platform,
                "python_version": sys.version,
                "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            }

            # Python runtime info
            system_info["python"] = {
                "version": sys.version_info[:3],
                "executable": sys.executable,
                "path": sys.path[:3],  # First 3 entries only
            }

            # Bot information
            if self.bot:
                system_info["bot"] = {
                    "ready": self.bot.is_ready(),
                    "user_id": self.bot.user.id if self.bot.user else None,
                    "guild_count": len(self.bot.guilds),
                    "latency": self.bot.latency,
                }

            return web.json_response(system_info)
        except Exception as e:
            return web.json_response(
                {
                    "error": f"System info failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )

    async def handle_runtime_info(self, request):
        """Runtime information endpoint."""
        try:
            runtime_info = {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime": time.time() - self.start_time,
                "memory": self._get_memory_info(),
                "environment": {},
                "configuration": {},
            }

            # Safe environment variables (non-sensitive)
            safe_env_vars = ["LOG_LEVEL", "REDIS_URL", "METRICS_PORT", "COOKIE_SOURCE"]
            for var in safe_env_vars:
                value = os.getenv(var)
                if value:
                    runtime_info["environment"][var] = value

            # Bot configuration (if available)
            if self.bot and hasattr(self.bot, "config"):
                # Only include non-sensitive config
                config = self.bot.config
                runtime_info["configuration"] = {
                    "platforms_enabled": len(config.get("platforms", {})),
                    "health_monitor_enabled": config.get("health_monitor", {}).get(
                        "enabled", False
                    ),
                    "cache_enabled": config.get("cache", {})
                    .get("redis", {})
                    .get("enabled", False),
                }

            return web.json_response(runtime_info)
        except Exception as e:
            return web.json_response(
                {
                    "error": f"Runtime info failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                status=500,
            )
