"""
HTTP server for exposing Prometheus metrics and comprehensive health check endpoints.
Enhanced version with dependency-free health checks for VPS deployment monitoring.
"""

# Import the enhanced metrics server for backward compatibility
from .enhanced_metrics_server import EnhancedMetricsServer

# Create alias for backward compatibility
MetricsServer = EnhancedMetricsServer
