#!/usr/bin/env python3
"""
Comprehensive deployment validation script for Robustty.
Uses the enhanced health check endpoints to validate deployment health.
"""

import sys
import json
import time
import urllib.request
import urllib.error
import socket
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import argparse


class DeploymentValidator:
    """Validates Robustty deployment using enhanced health endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.start_time = time.time()
        self.results = {
            'validation_start': datetime.utcnow().isoformat(),
            'base_url': base_url,
            'timeout': timeout,
            'checks': {},
            'overall_status': 'unknown',
            'summary': {}
        }
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")
    
    def make_request(self, endpoint: str, expected_status: int = 200) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Make HTTP request to health endpoint."""
        url = f"{self.base_url}{endpoint}"
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Robustty-DeploymentValidator/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == expected_status:
                    try:
                        data = json.loads(response.read().decode('utf-8'))
                        return True, data, f"HTTP {response.status}"
                    except json.JSONDecodeError as e:
                        return False, None, f"JSON decode error: {str(e)}"
                else:
                    return False, None, f"HTTP {response.status}"
                    
        except urllib.error.HTTPError as e:
            return False, None, f"HTTP Error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, None, f"URL Error: {str(e.reason)}"
        except socket.timeout:
            return False, None, "Request timeout"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"
    
    def wait_for_service(self, max_wait: int = 120) -> bool:
        """Wait for service to become available."""
        self.log(f"Waiting for service at {self.base_url} (max {max_wait}s)")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            success, data, message = self.make_request("/health")
            if success:
                self.log("Service is responding!")
                return True
            
            self.log(f"Service not ready: {message}, retrying in 5s...")
            time.sleep(5)
        
        self.log("Service failed to become available within timeout")
        return False
    
    def validate_basic_health(self) -> Dict[str, Any]:
        """Validate basic health endpoint."""
        self.log("Validating basic health...")
        
        success, data, message = self.make_request("/health")
        result = {
            'endpoint': '/health',
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success and data:
            status = data.get('status', 'unknown')
            result['health_status'] = status
            result['healthy'] = status in ['healthy', 'starting', 'degraded']
            
            if status == 'healthy':
                self.log("✓ Basic health check passed")
            elif status == 'starting':
                self.log("⚠ Service is starting up")
            elif status == 'degraded':
                self.log("⚠ Service is degraded but operational")
            else:
                self.log("✗ Basic health check failed")
        else:
            result['healthy'] = False
            self.log("✗ Basic health endpoint not accessible")
        
        return result
    
    def validate_readiness(self) -> Dict[str, Any]:
        """Validate readiness probe."""
        self.log("Validating readiness probe...")
        
        success, data, message = self.make_request("/ready")
        result = {
            'endpoint': '/ready',
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success and data:
            ready = data.get('ready', False)
            result['ready'] = ready
            
            if ready:
                self.log("✓ Readiness probe passed")
            else:
                self.log("✗ Readiness probe failed")
                checks = data.get('checks', {})
                for check_name, check_data in checks.items():
                    if not check_data.get('ready', True):
                        reason = check_data.get('reason', 'Unknown')
                        self.log(f"  - {check_name}: {reason}")
        else:
            result['ready'] = False
            self.log("✗ Readiness endpoint not accessible")
        
        return result
    
    def validate_liveness(self) -> Dict[str, Any]:
        """Validate liveness probe."""
        self.log("Validating liveness probe...")
        
        success, data, message = self.make_request("/live")
        result = {
            'endpoint': '/live',
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success and data:
            alive = data.get('alive', False)
            result['alive'] = alive
            
            if alive:
                self.log("✓ Liveness probe passed")
            else:
                self.log("✗ Liveness probe failed")
        else:
            result['alive'] = False
            self.log("✗ Liveness endpoint not accessible")
        
        return result
    
    def validate_detailed_health(self) -> Dict[str, Any]:
        """Validate detailed health status."""
        self.log("Validating detailed health status...")
        
        success, data, message = self.make_request("/health/detailed")
        result = {
            'endpoint': '/health/detailed',
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success and data:
            overall_status = data.get('overall_status', 'unknown')
            result['overall_status'] = overall_status
            result['healthy'] = overall_status in ['healthy', 'degraded']
            
            components = data.get('components', {})
            result['component_count'] = len(components)
            result['components'] = {}
            
            for component_name, component_data in components.items():
                component_status = component_data.get('status', 'unknown')
                result['components'][component_name] = component_status
                
                if component_status == 'healthy':
                    self.log(f"  ✓ {component_name}: healthy")
                elif component_status in ['degraded', 'warning']:
                    self.log(f"  ⚠ {component_name}: {component_status}")
                else:
                    self.log(f"  ✗ {component_name}: {component_status}")
                    if isinstance(component_data, dict) and 'message' in component_data:
                        self.log(f"    {component_data['message']}")
            
            if overall_status == 'healthy':
                self.log("✓ Detailed health check passed")
            elif overall_status == 'degraded':
                self.log("⚠ Detailed health shows degraded status")
            else:
                self.log("✗ Detailed health check failed")
        else:
            result['healthy'] = False
            self.log("✗ Detailed health endpoint not accessible")
        
        return result
    
    def validate_component_health(self, component: str) -> Dict[str, Any]:
        """Validate specific component health."""
        endpoint = f"/health/{component}"
        self.log(f"Validating {component} health...")
        
        success, data, message = self.make_request(endpoint)
        result = {
            'endpoint': endpoint,
            'component': component,
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success and data:
            status = data.get('status', 'unknown')
            result['status'] = status
            result['healthy'] = status in ['healthy', 'degraded']
            
            if status == 'healthy':
                self.log(f"✓ {component} health check passed")
            elif status == 'degraded':
                self.log(f"⚠ {component} health is degraded")
            else:
                self.log(f"✗ {component} health check failed")
                if 'message' in data:
                    self.log(f"  {data['message']}")
        else:
            result['healthy'] = False
            self.log(f"✗ {component} health endpoint not accessible")
        
        return result
    
    def validate_metrics_endpoint(self) -> Dict[str, Any]:
        """Validate Prometheus metrics endpoint."""
        self.log("Validating metrics endpoint...")
        
        success, data, message = self.make_request("/metrics")
        result = {
            'endpoint': '/metrics',
            'success': success,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            self.log("✓ Metrics endpoint accessible")
            result['accessible'] = True
        else:
            self.log("✗ Metrics endpoint not accessible")
            result['accessible'] = False
        
        return result
    
    def validate_security_basics(self) -> Dict[str, Any]:
        """Validate basic security health."""
        self.log("Validating security status...")
        
        success, data, message = self.make_request("/health/security")
        result = {
            'endpoint': '/health/security',
            'success': success,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success and data:
            status = data.get('status', 'unknown')
            result['status'] = status
            result['secure'] = status in ['healthy', 'warning']
            
            if status == 'healthy':
                self.log("✓ Security checks passed")
            elif status == 'warning':
                self.log("⚠ Security warnings detected")
            else:
                self.log("✗ Security issues detected")
                
            # Log specific security issues
            checks = data.get('checks', {})
            for check_name, check_data in checks.items():
                check_status = check_data.get('status', 'unknown')
                if check_status in ['warning', 'critical', 'error']:
                    issues = check_data.get('issues', [])
                    for issue in issues:
                        self.log(f"  Security {check_status}: {issue}")
        else:
            result['secure'] = False
            self.log("✗ Security health endpoint not accessible")
        
        return result
    
    def run_comprehensive_validation(self, wait_for_service: bool = True) -> Dict[str, Any]:
        """Run comprehensive deployment validation."""
        self.log("Starting comprehensive deployment validation...")
        
        # Wait for service if requested
        if wait_for_service and not self.wait_for_service():
            self.results['overall_status'] = 'failed'
            self.results['error'] = 'Service failed to become available'
            return self.results
        
        # Run all validation checks
        validation_checks = [
            ('basic_health', self.validate_basic_health),
            ('readiness', self.validate_readiness),
            ('liveness', self.validate_liveness),
            ('detailed_health', self.validate_detailed_health),
            ('discord_health', lambda: self.validate_component_health('discord')),
            ('platforms_health', lambda: self.validate_component_health('platforms')),
            ('performance_health', lambda: self.validate_component_health('performance')),
            ('infrastructure_health', lambda: self.validate_component_health('infrastructure')),
            ('metrics', self.validate_metrics_endpoint),
            ('security', self.validate_security_basics),
        ]
        
        passed_checks = 0
        failed_checks = 0
        warning_checks = 0
        
        for check_name, check_func in validation_checks:
            try:
                self.log(f"\n--- Running {check_name} validation ---")
                result = check_func()
                self.results['checks'][check_name] = result
                
                # Determine check status
                if result.get('success', False):
                    if result.get('healthy', True) or result.get('ready', True) or result.get('alive', True) or result.get('accessible', True) or result.get('secure', True):
                        passed_checks += 1
                    else:
                        warning_checks += 1
                else:
                    failed_checks += 1
                    
            except Exception as e:
                self.log(f"✗ {check_name} validation failed with exception: {str(e)}", "ERROR")
                self.results['checks'][check_name] = {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                failed_checks += 1
        
        # Calculate overall status
        total_checks = len(validation_checks)
        self.results['summary'] = {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': failed_checks,
            'warning_checks': warning_checks,
            'success_rate': passed_checks / total_checks * 100
        }
        
        if failed_checks == 0:
            if warning_checks == 0:
                self.results['overall_status'] = 'healthy'
                self.log("\n🎉 All validation checks passed!")
            else:
                self.results['overall_status'] = 'degraded'
                self.log(f"\n⚠ Validation completed with {warning_checks} warnings")
        else:
            self.results['overall_status'] = 'failed'
            self.log(f"\n❌ Validation failed: {failed_checks} checks failed")
        
        self.results['validation_duration'] = time.time() - self.start_time
        self.results['validation_end'] = datetime.utcnow().isoformat()
        
        return self.results


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate Robustty deployment health')
    parser.add_argument('--url', default='http://localhost:8080', 
                       help='Base URL for health checks (default: http://localhost:8080)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Timeout for requests in seconds (default: 30)')
    parser.add_argument('--wait', action='store_true',
                       help='Wait for service to become available before validation')
    parser.add_argument('--output', choices=['json', 'text'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(base_url=args.url, timeout=args.timeout)
    
    try:
        results = validator.run_comprehensive_validation(wait_for_service=args.wait)
        
        if args.output == 'json':
            print(json.dumps(results, indent=2))
        
        # Exit with appropriate code
        if results['overall_status'] == 'healthy':
            sys.exit(0)
        elif results['overall_status'] == 'degraded':
            sys.exit(1)
        else:
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Validation failed with unexpected error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(3)


if __name__ == '__main__':
    main()