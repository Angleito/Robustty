#!/usr/bin/env python3
"""
Dependency-free health check script for Docker health checks.
This script performs basic health checks without requiring external libraries.
"""

import sys
import json
import socket
import time
import os
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional


def check_port_open(host: str, port: int, timeout: int = 5) -> bool:
    """Check if a port is open on the given host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_http_endpoint(url: str, timeout: int = 5) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if HTTP endpoint is responding and return health data."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Robustty-HealthCheck/1.0')
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                try:
                    data = json.loads(response.read().decode('utf-8'))
                    return True, data
                except json.JSONDecodeError:
                    return True, None
            else:
                return False, None
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout):
        return False, None


def check_memory_usage() -> Dict[str, Any]:
    """Check memory usage without external dependencies."""
    try:
        # Try to read from /proc/meminfo (Linux)
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        
        mem_info = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                # Extract numeric value (assume kB)
                value_parts = value.strip().split()
                if value_parts and value_parts[0].isdigit():
                    mem_info[key.strip()] = int(value_parts[0]) * 1024  # Convert to bytes
        
        total = mem_info.get('MemTotal', 0)
        available = mem_info.get('MemAvailable', mem_info.get('MemFree', 0))
        used = total - available
        percent = (used / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'used': used,
            'available': available,
            'percent': percent
        }
    except (FileNotFoundError, PermissionError, OSError):
        # Fallback - return safe values
        return {'total': 0, 'used': 0, 'available': 0, 'percent': 0}


def check_disk_usage(path: str = '/') -> Dict[str, Any]:
    """Check disk usage for given path."""
    try:
        import shutil
        usage = shutil.disk_usage(path)
        percent = (usage.used / usage.total * 100) if usage.total > 0 else 0
        return {
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'percent': percent
        }
    except (ImportError, OSError):
        return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}


def check_discord_connectivity() -> bool:
    """Check basic Discord connectivity."""
    discord_endpoints = [
        ('gateway-us-east1-a.discord.gg', 443),
        ('gateway-us-west1-a.discord.gg', 443),
        ('discord.com', 443)
    ]
    
    for host, port in discord_endpoints:
        if check_port_open(host, port, timeout=10):
            return True
    
    return False


def perform_basic_health_check() -> Dict[str, Any]:
    """Perform comprehensive basic health check."""
    health_data = {
        'timestamp': time.time(),
        'status': 'healthy',
        'checks': {}
    }
    
    # Check local health endpoint
    health_endpoint_ok, endpoint_data = check_http_endpoint('http://localhost:8080/health', timeout=5)
    health_data['checks']['health_endpoint'] = {
        'status': 'pass' if health_endpoint_ok else 'fail',
        'data': endpoint_data
    }
    
    # Check metrics endpoint
    metrics_ok, _ = check_http_endpoint('http://localhost:8080/metrics', timeout=5)
    health_data['checks']['metrics_endpoint'] = {
        'status': 'pass' if metrics_ok else 'fail'
    }
    
    # Check memory usage
    memory_info = check_memory_usage()
    memory_ok = memory_info['percent'] < 90
    health_data['checks']['memory'] = {
        'status': 'pass' if memory_ok else 'fail',
        'usage_percent': memory_info['percent'],
        'used_bytes': memory_info['used'],
        'total_bytes': memory_info['total']
    }
    
    # Check disk usage
    disk_info = check_disk_usage('/')
    disk_ok = disk_info['percent'] < 95
    health_data['checks']['disk'] = {
        'status': 'pass' if disk_ok else 'fail',
        'usage_percent': disk_info['percent'],
        'free_bytes': disk_info['free']
    }
    
    # Check Discord connectivity
    discord_ok = check_discord_connectivity()
    health_data['checks']['discord_connectivity'] = {
        'status': 'pass' if discord_ok else 'fail'
    }
    
    # Check Redis connectivity (if configured)
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_ok = check_port_open(redis_host, redis_port, timeout=3)
    health_data['checks']['redis_connectivity'] = {
        'status': 'pass' if redis_ok else 'warn',  # Redis is optional
        'host': redis_host,
        'port': redis_port
    }
    
    # Determine overall status
    failed_checks = [
        check for check in health_data['checks'].values() 
        if check['status'] == 'fail'
    ]
    
    if failed_checks:
        health_data['status'] = 'unhealthy'
        health_data['failed_checks'] = len(failed_checks)
    elif any(check['status'] == 'warn' for check in health_data['checks'].values()):
        health_data['status'] = 'degraded'
    
    return health_data


def perform_readiness_check() -> Dict[str, Any]:
    """Perform readiness check - more strict than basic health."""
    ready_data = {
        'timestamp': time.time(),
        'ready': True,
        'checks': {}
    }
    
    # Check if application is responding
    health_ok, health_response = check_http_endpoint('http://localhost:8080/ready', timeout=10)
    if health_ok and health_response:
        ready_data['checks']['application'] = {
            'status': 'pass',
            'ready': health_response.get('ready', False)
        }
        if not health_response.get('ready', False):
            ready_data['ready'] = False
    else:
        ready_data['checks']['application'] = {'status': 'fail'}
        ready_data['ready'] = False
    
    # Check critical resource usage
    memory_info = check_memory_usage()
    memory_ready = memory_info['percent'] < 85
    ready_data['checks']['memory'] = {
        'status': 'pass' if memory_ready else 'fail',
        'usage_percent': memory_info['percent']
    }
    if not memory_ready:
        ready_data['ready'] = False
    
    # Check Discord connectivity (critical for readiness)
    discord_ok = check_discord_connectivity()
    ready_data['checks']['discord'] = {'status': 'pass' if discord_ok else 'fail'}
    if not discord_ok:
        ready_data['ready'] = False
    
    return ready_data


def perform_liveness_check() -> Dict[str, Any]:
    """Perform liveness check - basic process health."""
    alive_data = {
        'timestamp': time.time(),
        'alive': True,
        'checks': {}
    }
    
    # Check if we can reach the liveness endpoint
    alive_ok, alive_response = check_http_endpoint('http://localhost:8080/live', timeout=5)
    if alive_ok and alive_response:
        alive_data['checks']['application'] = {
            'status': 'pass',
            'alive': alive_response.get('alive', False)
        }
        if not alive_response.get('alive', False):
            alive_data['alive'] = False
    else:
        alive_data['checks']['application'] = {'status': 'fail'}
        alive_data['alive'] = False
    
    # Check for memory exhaustion (more lenient than readiness)
    memory_info = check_memory_usage()
    memory_alive = memory_info['percent'] < 98
    alive_data['checks']['memory'] = {
        'status': 'pass' if memory_alive else 'fail',
        'usage_percent': memory_info['percent']
    }
    if not memory_alive:
        alive_data['alive'] = False
    
    return alive_data


def main():
    """Main health check function."""
    if len(sys.argv) < 2:
        print("Usage: health-check.py <check_type>")
        print("Check types: basic, ready, live")
        sys.exit(1)
    
    check_type = sys.argv[1].lower()
    
    try:
        if check_type == 'basic':
            result = perform_basic_health_check()
            success = result['status'] in ['healthy', 'degraded']
        elif check_type == 'ready':
            result = perform_readiness_check()
            success = result['ready']
        elif check_type == 'live':
            result = perform_liveness_check()
            success = result['alive']
        else:
            print(f"Unknown check type: {check_type}")
            sys.exit(1)
        
        # Output result as JSON
        print(json.dumps(result, indent=2))
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        error_result = {
            'timestamp': time.time(),
            'status': 'error',
            'error': str(e),
            'check_type': check_type
        }
        print(json.dumps(error_result, indent=2))
        sys.exit(2)


if __name__ == '__main__':
    main()