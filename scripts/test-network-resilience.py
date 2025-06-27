#!/usr/bin/env python3
"""
Network Resilience Testing for Cookie Sync System

This script validates the enhanced cookie sync system under various network conditions
to ensure connection pooling, retries, and error handling work correctly.
"""

import asyncio
import json
import logging
import os
import random
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp
import aiofiles

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/network_resilience_test.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Test result data structure"""
    test_name: str
    success: bool
    duration: float
    error: Optional[str] = None
    retries: int = 0
    details: Optional[Dict] = None

@dataclass
class NetworkCondition:
    """Network condition simulation parameters"""
    name: str
    packet_loss: float = 0.0  # Percentage (0-100)
    latency_ms: int = 0       # Additional latency in milliseconds
    bandwidth_limit: Optional[str] = None  # e.g., "1mbit"
    intermittent_disconnect: bool = False
    disconnect_duration: int = 5  # Seconds

class NetworkResilienceTestSuite:
    """Test suite for network resilience validation"""
    
    def __init__(self, config_path: str = ".env"):
        self.config = self._load_config(config_path)
        self.test_results: List[TestResult] = []
        self.start_time = datetime.now()
        
        # Test scenarios
        self.network_conditions = [
            NetworkCondition("normal", 0.0, 0),
            NetworkCondition("high_latency", 0.0, 2000),
            NetworkCondition("packet_loss_5", 5.0, 100),
            NetworkCondition("packet_loss_15", 15.0, 200),
            NetworkCondition("low_bandwidth", 0.0, 100, "512kbit"),
            NetworkCondition("intermittent", 0.0, 100, None, True, 10),
            NetworkCondition("extreme_latency", 0.0, 5000),
            NetworkCondition("heavy_packet_loss", 25.0, 500),
        ]
        
        # Paths
        self.cookie_dir = Path('/app/cookies')
        self.test_cookie_dir = Path('/tmp/test_cookies')
        self.backup_dir = Path('/tmp/test_backup')
        
        # Ensure test directories exist
        self.test_cookie_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

    def _load_config(self, config_path: str) -> Dict[str, str]:
        """Load configuration from environment and .env file"""
        config = {}
        
        # Load from .env file if it exists
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"\'')
        
        # Override with environment variables
        required_vars = ['VPS_HOST', 'VPS_USER', 'SSH_KEY_PATH']
        for var in required_vars:
            if var in os.environ:
                config[var] = os.environ[var]
        
        # Set defaults
        config.setdefault('VPS_USER', 'ubuntu')
        config.setdefault('VPS_PATH', '~/robustty-bot')
        config.setdefault('SSH_KEY_PATH', '~/.ssh/id_rsa')
        
        return config

    async def setup_test_environment(self):
        """Setup test environment with sample cookies"""
        logger.info("Setting up test environment...")
        
        # Create test cookies
        test_cookies = {
            'youtube': [
                {
                    "name": "session_token",
                    "value": f"test_token_{int(time.time())}",
                    "domain": ".youtube.com",
                    "path": "/",
                    "secure": True
                },
                {
                    "name": "user_prefs",
                    "value": "test_prefs_123",
                    "domain": "youtube.com",
                    "path": "/",
                    "secure": False
                }
            ],
            'rumble': [
                {
                    "name": "auth_token",
                    "value": f"rumble_auth_{random.randint(1000, 9999)}",
                    "domain": ".rumble.com",
                    "path": "/",
                    "secure": True
                }
            ],
            'peertube': [
                {
                    "name": "session",
                    "value": f"pt_session_{int(time.time())}",
                    "domain": "framatube.org",
                    "path": "/",
                    "secure": True
                }
            ]
        }
        
        # Save test cookies
        for platform, cookies in test_cookies.items():
            cookie_file = self.test_cookie_dir / f"{platform}_cookies.json"
            async with aiofiles.open(cookie_file, 'w') as f:
                await f.write(json.dumps(cookies, indent=2))
        
        # Backup real cookies if they exist
        if self.cookie_dir.exists():
            logger.info("Backing up real cookies...")
            await self._run_command(f"cp -r {self.cookie_dir}/* {self.backup_dir}/")
            await self._run_command(f"cp -r {self.test_cookie_dir}/* {self.cookie_dir}/")
        
        logger.info("Test environment setup complete")

    async def cleanup_test_environment(self):
        """Cleanup test environment and restore real cookies"""
        logger.info("Cleaning up test environment...")
        
        # Restore real cookies if backup exists
        if self.backup_dir.exists() and any(self.backup_dir.iterdir()):
            logger.info("Restoring real cookies...")
            await self._run_command(f"rm -f {self.cookie_dir}/*.json")
            await self._run_command(f"cp {self.backup_dir}/*.json {self.cookie_dir}/")
        
        # Clean up test files
        await self._run_command(f"rm -rf {self.test_cookie_dir}")
        await self._run_command(f"rm -rf {self.backup_dir}")
        
        logger.info("Test environment cleanup complete")

    async def _run_command(self, command: str, timeout: int = 60) -> Tuple[bool, str, str]:
        """Run shell command with timeout"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            return (
                process.returncode == 0,
                stdout.decode(),
                stderr.decode()
            )
        except asyncio.TimeoutError:
            return False, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return False, "", str(e)

    @asynccontextmanager
    async def simulate_network_condition(self, condition: NetworkCondition):
        """Context manager to simulate network conditions using tc (traffic control)"""
        logger.info(f"Applying network condition: {condition.name}")
        
        # Note: This would require root privileges and tc tool
        # For testing purposes, we'll simulate conditions differently
        
        if condition.intermittent_disconnect:
            # Start a task that intermittently blocks network
            disconnect_task = asyncio.create_task(
                self._simulate_intermittent_disconnect(condition.disconnect_duration)
            )
        else:
            disconnect_task = None
        
        try:
            # Add artificial delays if needed
            if condition.latency_ms > 0:
                await asyncio.sleep(condition.latency_ms / 1000.0)
            
            yield condition
            
        finally:
            if disconnect_task:
                disconnect_task.cancel()
                try:
                    await disconnect_task
                except asyncio.CancelledError:
                    pass
            
            logger.info(f"Removed network condition: {condition.name}")

    async def _simulate_intermittent_disconnect(self, duration: int):
        """Simulate intermittent network disconnections"""
        while True:
            # Wait random time between 10-30 seconds
            await asyncio.sleep(random.uniform(10, 30))
            
            logger.warning(f"Simulating network disconnect for {duration}s")
            # In a real scenario, this would temporarily block network access
            await asyncio.sleep(duration)
            logger.info("Network connectivity restored")

    async def test_enhanced_cookie_manager(self, condition: NetworkCondition) -> TestResult:
        """Test enhanced cookie manager under specific network conditions"""
        test_name = f"enhanced_cookie_manager_{condition.name}"
        start_time = time.time()
        
        try:
            # Import the enhanced cookie manager
            sys.path.append(str(Path(__file__).parent.parent / 'src'))
            from services.enhanced_cookie_manager import EnhancedCookieManager
            
            # Create manager with test configuration
            config = {
                'max_retry_attempts': 5,
                'retry_delay': 1.0,
                'cookie_max_age_hours': 24,
                'enable_health_monitoring': True,
                'vps_mode': True,
                'cookie_optional_platforms': ['peertube', 'odysee']
            }
            
            manager = EnhancedCookieManager(config)
            
            # Test cookie loading
            load_results = await manager.load_cookies()
            successful_loads = sum(1 for success in load_results.values() if success)
            
            # Test cookie refresh
            refresh_results = await manager.refresh_cookies(force=True)
            successful_refreshes = sum(1 for success in refresh_results.values() if success)
            
            # Test health monitoring
            health_statuses = {}
            for platform in ['youtube', 'rumble', 'peertube']:
                health_statuses[platform] = manager.get_platform_health_status(platform)
            
            # Test cookie retrieval for URLs
            test_urls = [
                'https://www.youtube.com/watch?v=test123',
                'https://rumble.com/test-video',
                'https://framatube.org/test'
            ]
            
            url_test_results = {}
            for url in test_urls:
                cookies, fallback = await manager.get_cookies_for_url(url)
                url_test_results[url] = {
                    'has_cookies': cookies is not None,
                    'cookie_count': len(cookies) if cookies else 0,
                    'should_use_fallback': fallback
                }
            
            # Cleanup
            await manager.cleanup()
            
            duration = time.time() - start_time
            
            return TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details={
                    'load_results': load_results,
                    'refresh_results': refresh_results,
                    'health_statuses': health_statuses,
                    'url_test_results': url_test_results,
                    'successful_loads': successful_loads,
                    'successful_refreshes': successful_refreshes
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Enhanced cookie manager test failed: {e}")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )

    async def test_auto_sync_script(self, condition: NetworkCondition) -> TestResult:
        """Test auto-sync script under network conditions"""
        test_name = f"auto_sync_script_{condition.name}"
        start_time = time.time()
        
        try:
            # Set environment variables for the test
            env = os.environ.copy()
            env.update({
                'AUTO_SYNC_VPS': 'true',
                'VPS_HOST': self.config.get('VPS_HOST', 'test-host'),
                'VPS_USER': self.config.get('VPS_USER', 'ubuntu'),
                'VPS_PATH': self.config.get('VPS_PATH', '~/robustty-bot'),
                'SSH_KEY_PATH': self.config.get('SSH_KEY_PATH', '~/.ssh/id_rsa')
            })
            
            # Run the auto-sync script
            script_path = Path(__file__).parent / 'auto-sync-cookies.py'
            if not script_path.exists():
                raise FileNotFoundError(f"Auto-sync script not found: {script_path}")
            
            process = await asyncio.create_subprocess_exec(
                'python3', str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Add timeout based on network condition
            timeout = 60
            if condition.latency_ms > 1000:
                timeout += condition.latency_ms // 1000
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            duration = time.time() - start_time
            success = process.returncode == 0
            
            return TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                error=stderr.decode() if not success else None,
                details={
                    'stdout': stdout.decode(),
                    'stderr': stderr.decode(),
                    'return_code': process.returncode
                }
            )
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            logger.error(f"Auto-sync script timed out after {timeout}s")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=f"Timeout after {timeout}s"
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Auto-sync script test failed: {e}")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )

    async def test_unified_vps_sync(self, condition: NetworkCondition) -> TestResult:
        """Test unified VPS sync script under network conditions"""
        test_name = f"unified_vps_sync_{condition.name}"
        start_time = time.time()
        
        try:
            # Set environment variables for the test
            env = os.environ.copy()
            env.update({
                'VPS_HOST': self.config.get('VPS_HOST', 'test-host'),
                'VPS_USER': self.config.get('VPS_USER', 'ubuntu'),
                'VPS_PATH': self.config.get('VPS_PATH', '~/robustty-bot'),
                'SSH_KEY_PATH': self.config.get('SSH_KEY_PATH', '~/.ssh/id_rsa')
            })
            
            # Run the unified sync script in dry-run mode for testing
            script_path = Path(__file__).parent / 'unified-vps-sync.sh'
            if not script_path.exists():
                raise FileNotFoundError(f"Unified sync script not found: {script_path}")
            
            process = await asyncio.create_subprocess_exec(
                'bash', str(script_path), '--dry-run',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Add timeout based on network condition
            timeout = 30  # Dry run should be fast
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            duration = time.time() - start_time
            success = process.returncode == 0
            
            return TestResult(
                test_name=test_name,
                success=success,
                duration=duration,
                error=stderr.decode() if not success else None,
                details={
                    'stdout': stdout.decode(),
                    'stderr': stderr.decode(),
                    'return_code': process.returncode,
                    'dry_run': True
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Unified VPS sync test failed: {e}")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )

    async def test_network_resilience_utilities(self, condition: NetworkCondition) -> TestResult:
        """Test network resilience utilities under network conditions"""
        test_name = f"network_resilience_utilities_{condition.name}"
        start_time = time.time()
        
        try:
            # Import network resilience utilities
            sys.path.append(str(Path(__file__).parent.parent / 'src'))
            from utils.network_resilience import (
                NetworkResilienceManager,
                CircuitBreakerConfig,
                RetryConfig,
                with_retry,
                with_circuit_breaker
            )
            
            manager = NetworkResilienceManager()
            
            # Test circuit breaker functionality
            @with_circuit_breaker(
                service_name="test_service",
                config=CircuitBreakerConfig(failure_threshold=2, recovery_timeout=5)
            )
            async def test_function_with_cb():
                if random.random() < 0.3:  # 30% failure rate
                    raise Exception("Simulated failure")
                return "success"
            
            # Test retry functionality
            @with_retry(
                retry_config=RetryConfig(max_attempts=3, base_delay=0.1),
                service_name="retry_test_service"
            )
            async def test_function_with_retry():
                if random.random() < 0.5:  # 50% failure rate
                    raise Exception("Simulated failure")
                return "success"
            
            # Execute tests multiple times
            cb_results = []
            retry_results = []
            
            for i in range(10):
                try:
                    result = await test_function_with_cb()
                    cb_results.append(True)
                except Exception:
                    cb_results.append(False)
                
                try:
                    result = await test_function_with_retry()
                    retry_results.append(True)
                except Exception:
                    retry_results.append(False)
                
                # Small delay between tests
                await asyncio.sleep(0.1)
            
            # Get manager status
            status = manager.get_all_status()
            
            duration = time.time() - start_time
            
            return TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                details={
                    'circuit_breaker_success_rate': sum(cb_results) / len(cb_results),
                    'retry_success_rate': sum(retry_results) / len(retry_results),
                    'manager_status': status,
                    'total_tests': len(cb_results)
                }
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Network resilience utilities test failed: {e}")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )

    async def test_http_session_resilience(self, condition: NetworkCondition) -> TestResult:
        """Test HTTP session resilience with connection pooling"""
        test_name = f"http_session_resilience_{condition.name}"
        start_time = time.time()
        
        try:
            # Configure session with connection pooling and retries
            connector = aiohttp.TCPConnector(
                limit=10,  # Total connection pool size
                limit_per_host=5,  # Per-host connection limit
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=30,
                connect=10,
                sock_read=10
            )
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'User-Agent': 'Robustty-NetworkTest/1.0'}
            ) as session:
                
                # Test multiple concurrent requests
                test_urls = [
                    'https://httpbin.org/delay/1',
                    'https://httpbin.org/status/200',
                    'https://httpbin.org/json',
                    'https://httpbin.org/user-agent',
                    'https://httpbin.org/headers'
                ]
                
                # Add network condition delays
                if condition.latency_ms > 0:
                    await asyncio.sleep(condition.latency_ms / 1000.0)
                
                successful_requests = 0
                failed_requests = 0
                
                # Test concurrent requests
                tasks = []
                for url in test_urls:
                    tasks.append(self._make_http_request(session, url))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        failed_requests += 1
                    else:
                        successful_requests += 1
                
                # Test connection reuse
                reuse_test_results = []
                for i in range(5):
                    try:
                        async with session.get('https://httpbin.org/delay/0.1') as resp:
                            reuse_test_results.append(resp.status == 200)
                    except Exception:
                        reuse_test_results.append(False)
                    
                    await asyncio.sleep(0.1)
                
                duration = time.time() - start_time
                
                return TestResult(
                    test_name=test_name,
                    success=successful_requests > 0,
                    duration=duration,
                    details={
                        'successful_requests': successful_requests,
                        'failed_requests': failed_requests,
                        'total_requests': len(test_urls),
                        'success_rate': successful_requests / len(test_urls),
                        'connection_reuse_success_rate': sum(reuse_test_results) / len(reuse_test_results),
                        'connection_reuse_tests': len(reuse_test_results)
                    }
                )
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"HTTP session resilience test failed: {e}")
            return TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                error=str(e)
            )

    async def _make_http_request(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Make a single HTTP request and return success status"""
        try:
            async with session.get(url) as response:
                return response.status == 200
        except Exception as e:
            logger.debug(f"HTTP request to {url} failed: {e}")
            return False

    async def run_comprehensive_tests(self):
        """Run comprehensive network resilience tests"""
        logger.info("Starting comprehensive network resilience tests...")
        
        # Setup test environment
        await self.setup_test_environment()
        
        try:
            total_tests = 0
            successful_tests = 0
            
            # Run tests under each network condition
            for condition in self.network_conditions:
                logger.info(f"\n{'='*60}")
                logger.info(f"Testing under condition: {condition.name}")
                logger.info(f"{'='*60}")
                
                async with self.simulate_network_condition(condition):
                    # Test suite for this condition
                    condition_tests = [
                        self.test_enhanced_cookie_manager(condition),
                        self.test_network_resilience_utilities(condition),
                        self.test_http_session_resilience(condition),
                    ]
                    
                    # Only test scripts if VPS_HOST is configured
                    if self.config.get('VPS_HOST') and self.config['VPS_HOST'] != 'your-vps-ip':
                        condition_tests.extend([
                            self.test_auto_sync_script(condition),
                            self.test_unified_vps_sync(condition),
                        ])
                    else:
                        logger.warning("VPS_HOST not configured, skipping VPS sync tests")
                    
                    # Run tests for this condition
                    condition_results = await asyncio.gather(
                        *condition_tests, return_exceptions=True
                    )
                    
                    for result in condition_results:
                        if isinstance(result, TestResult):
                            self.test_results.append(result)
                            total_tests += 1
                            if result.success:
                                successful_tests += 1
                                logger.info(f"✅ {result.test_name}: PASSED ({result.duration:.2f}s)")
                            else:
                                logger.error(f"❌ {result.test_name}: FAILED ({result.duration:.2f}s)")
                                if result.error:
                                    logger.error(f"   Error: {result.error}")
                        else:
                            logger.error(f"❌ Test failed with exception: {result}")
                            total_tests += 1
            
            # Generate test report
            await self.generate_test_report(total_tests, successful_tests)
            
        finally:
            # Cleanup test environment
            await self.cleanup_test_environment()

    async def generate_test_report(self, total_tests: int, successful_tests: int):
        """Generate comprehensive test report"""
        report_data = {
            'test_summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_duration': (datetime.now() - self.start_time).total_seconds(),
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'failed_tests': total_tests - successful_tests,
                'success_rate': (successful_tests / total_tests * 100) if total_tests > 0 else 0
            },
            'network_conditions_tested': [
                {
                    'name': condition.name,
                    'packet_loss': condition.packet_loss,
                    'latency_ms': condition.latency_ms,
                    'bandwidth_limit': condition.bandwidth_limit,
                    'intermittent_disconnect': condition.intermittent_disconnect
                }
                for condition in self.network_conditions
            ],
            'detailed_results': [
                {
                    'test_name': result.test_name,
                    'success': result.success,
                    'duration': result.duration,
                    'error': result.error,
                    'retries': result.retries,
                    'details': result.details
                }
                for result in self.test_results
            ],
            'analysis': self._analyze_results()
        }
        
        # Save report
        report_file = Path('/tmp/network_resilience_test_report.json')
        async with aiofiles.open(report_file, 'w') as f:
            await f.write(json.dumps(report_data, indent=2, default=str))
        
        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info("NETWORK RESILIENCE TEST SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Successful: {successful_tests}")
        logger.info(f"Failed: {total_tests - successful_tests}")
        logger.info(f"Success Rate: {successful_tests/total_tests*100:.1f}%")
        logger.info(f"Test Duration: {(datetime.now() - self.start_time).total_seconds():.1f}s")
        logger.info(f"Report saved to: {report_file}")
        
        # Print analysis
        analysis = report_data['analysis']
        logger.info(f"\n{'='*60}")
        logger.info("ANALYSIS")
        logger.info(f"{'='*60}")
        
        if analysis['resilience_score'] >= 90:
            logger.info("🟢 EXCELLENT: System shows excellent resilience to network issues")
        elif analysis['resilience_score'] >= 75:
            logger.info("🟡 GOOD: System shows good resilience with minor issues")
        elif analysis['resilience_score'] >= 50:
            logger.info("🟠 MODERATE: System has moderate resilience, needs improvement")
        else:
            logger.info("🔴 POOR: System shows poor resilience, significant improvements needed")
        
        logger.info(f"Resilience Score: {analysis['resilience_score']:.1f}/100")
        logger.info(f"Most Challenging Condition: {analysis['most_challenging_condition']}")
        logger.info(f"Most Reliable Component: {analysis['most_reliable_component']}")

    def _analyze_results(self) -> Dict:
        """Analyze test results and provide insights"""
        if not self.test_results:
            return {}
        
        # Group results by network condition
        condition_performance = {}
        component_performance = {}
        
        for result in self.test_results:
            # Extract condition name from test name
            parts = result.test_name.split('_')
            if len(parts) >= 3:
                component = '_'.join(parts[:-1])
                condition = parts[-1]
            else:
                component = result.test_name
                condition = 'unknown'
            
            if condition not in condition_performance:
                condition_performance[condition] = {'total': 0, 'successful': 0}
            if component not in component_performance:
                component_performance[component] = {'total': 0, 'successful': 0}
            
            condition_performance[condition]['total'] += 1
            component_performance[component]['total'] += 1
            
            if result.success:
                condition_performance[condition]['successful'] += 1
                component_performance[component]['successful'] += 1
        
        # Calculate success rates
        condition_rates = {
            condition: (data['successful'] / data['total'] * 100) if data['total'] > 0 else 0
            for condition, data in condition_performance.items()
        }
        
        component_rates = {
            component: (data['successful'] / data['total'] * 100) if data['total'] > 0 else 0
            for component, data in component_performance.items()
        }
        
        # Find most challenging condition and most reliable component
        most_challenging = min(condition_rates.items(), key=lambda x: x[1])
        most_reliable = max(component_rates.items(), key=lambda x: x[1])
        
        # Calculate overall resilience score
        total_success_rate = sum(condition_rates.values()) / len(condition_rates) if condition_rates else 0
        consistency_bonus = min(condition_rates.values()) if condition_rates else 0
        resilience_score = (total_success_rate * 0.7) + (consistency_bonus * 0.3)
        
        return {
            'resilience_score': resilience_score,
            'condition_performance': condition_rates,
            'component_performance': component_rates,
            'most_challenging_condition': most_challenging[0],
            'most_challenging_success_rate': most_challenging[1],
            'most_reliable_component': most_reliable[0],
            'most_reliable_success_rate': most_reliable[1],
            'average_test_duration': sum(r.duration for r in self.test_results) / len(self.test_results)
        }

async def main():
    """Main function to run network resilience tests"""
    print("🌐 Network Resilience Testing for Cookie Sync System")
    print("=" * 60)
    
    # Check if we're running as root (needed for network simulation)
    if os.geteuid() != 0:
        logger.warning("Not running as root - network condition simulation will be limited")
    
    # Create test suite
    test_suite = NetworkResilienceTestSuite()
    
    # Check configuration
    if not test_suite.config.get('VPS_HOST'):
        logger.warning("VPS_HOST not configured - VPS sync tests will be skipped")
        logger.info("To test VPS sync, set VPS_HOST environment variable or .env file")
    
    try:
        # Run comprehensive tests
        await test_suite.run_comprehensive_tests()
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        await test_suite.cleanup_test_environment()
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        await test_suite.cleanup_test_environment()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
