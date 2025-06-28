#!/usr/bin/env python3
"""
Test script to verify enhanced voice connection manager functionality
"""

import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

# Import only what we need to avoid discord dependency
import importlib.util
spec = importlib.util.spec_from_file_location(
    "voice_connection_manager", 
    os.path.join(os.path.dirname(__file__), "src/services/voice_connection_manager.py")
)
vcm_module = importlib.util.module_from_spec(spec)

# Mock discord before loading
sys.modules['discord'] = Mock()
sys.modules['discord.ext'] = Mock()
sys.modules['discord.ext.commands'] = Mock()
sys.modules['aiohttp'] = Mock()

# Now load the module
spec.loader.exec_module(vcm_module)

VoiceConnectionManager = vcm_module.VoiceConnectionManager
VoiceConnectionState = vcm_module.VoiceConnectionState
DeploymentEnvironment = vcm_module.DeploymentEnvironment


class TestVoiceConnectionManager:
    """Test the enhanced voice connection manager"""
    
    def __init__(self):
        # Create mock bot
        self.bot = Mock()
        self.bot.get_guild = Mock(return_value=None)
        
        # Temporarily override _start_health_monitoring to prevent task creation
        original_start = VoiceConnectionManager._start_health_monitoring
        VoiceConnectionManager._start_health_monitoring = lambda self: None
        
        # Create voice manager
        self.voice_manager = VoiceConnectionManager(self.bot)
        
        # Restore original method
        VoiceConnectionManager._start_health_monitoring = original_start
        
    def test_environment_detection(self):
        """Test environment detection"""
        print("\n🔍 Testing Environment Detection...")
        
        env = self.voice_manager.environment
        print(f"Detected environment: {env.value}")
        
        # Check configuration based on environment
        if env == DeploymentEnvironment.VPS:
            print("✅ VPS environment detected - using extended timeouts")
            assert self.voice_manager.max_retry_attempts == 3  # Reduced for faster recovery
            assert self.voice_manager.base_retry_delay == 8.0  # Discord requires 6+ seconds
            assert self.voice_manager.connection_timeout == 60.0  # Longer timeout for VPS
        else:
            print(f"✅ {env.value} environment detected - using standard timeouts")
            assert self.voice_manager.max_retry_attempts == 5
            assert self.voice_manager.base_retry_delay == 2.0
            assert self.voice_manager.connection_timeout == 30.0
            
    def test_retry_delay_calculation(self):
        """Test exponential backoff calculation"""
        print("\n⏱️ Testing Retry Delay Calculation...")
        
        delays = []
        for attempt in range(1, 6):
            delay = self.voice_manager._calculate_retry_delay(attempt)
            delays.append(delay)
            print(f"Attempt {attempt}: {delay:.1f}s delay")
            
        # Verify exponential growth (with allowance for jitter and max delay cap)
        # First few should increase, then may cap at max_retry_delay
        assert delays[1] > delays[0] * 1.5, "Second delay should be roughly double the first"
        # After hitting max, delays should be close to max_retry_delay
        max_delay = self.voice_manager.max_retry_delay
        for i in range(2, len(delays)):
            if delays[i] >= max_delay * 0.9:  # Within 10% of max delay
                print(f"✅ Delay {i+1} has reached max delay cap")
            else:
                assert delays[i] >= delays[i-1] * 0.9, f"Delay {i+1} should be at least 90% of delay {i} (accounting for jitter)"
            
        print("✅ Exponential backoff working correctly")
        
    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        print("\n🚨 Testing Circuit Breaker...")
        
        guild_id = 12345
        
        # Test initial state - circuit should be closed
        assert not self.voice_manager._is_circuit_open(guild_id)
        print("✅ Circuit initially closed")
        
        # Record failures up to threshold
        for i in range(self.voice_manager.circuit_breaker_threshold):
            self.voice_manager._record_failure(guild_id)
            
        # Circuit should now be open
        assert self.voice_manager._is_circuit_open(guild_id)
        print(f"✅ Circuit opened after {self.voice_manager.circuit_breaker_threshold} failures")
        
        # Record success should clear failures
        self.voice_manager._record_success(guild_id)
        assert not self.voice_manager._is_circuit_open(guild_id)
        print("✅ Circuit closed after success")
        
    def test_session_management(self):
        """Test session creation and validation"""
        print("\n🔐 Testing Session Management...")
        
        guild_id = 12345
        
        # Test no session initially
        assert not self.voice_manager._is_session_valid(guild_id)
        print("✅ No session initially")
        
        # Create session
        asyncio.run(self.voice_manager._create_new_session(guild_id))
        assert self.voice_manager._is_session_valid(guild_id)
        session = self.voice_manager.session_states[guild_id]
        print(f"✅ Session created: {session['session_id']}")
        
        # Test session info in connection info
        info = self.voice_manager.get_connection_info(guild_id)
        assert 'session' in info
        assert info['session']['id'] == session['session_id']
        print("✅ Session info available in connection info")
        
    async def test_error_handling(self):
        """Test error handling for different error codes"""
        print("\n❌ Testing Error Handling...")
        
        guild_id = 12345
        
        # Create a proper mock for discord.ConnectionClosed
        class MockConnectionClosed(Exception):
            def __init__(self, code):
                self.code = code
        
        # Temporarily set discord.ConnectionClosed to our mock class
        original = sys.modules['discord'].ConnectionClosed
        sys.modules['discord'].ConnectionClosed = MockConnectionClosed
        
        try:
            # Test WebSocket error 4006 (session invalid)
            error_4006 = MockConnectionClosed(4006)
            should_retry, needs_session = await self.voice_manager._handle_voice_connection_error(
                guild_id, error_4006
            )
            
            assert should_retry == True
            assert needs_session == True
            print("✅ Error 4006 triggers retry with new session")
            
            # Test error 4014 (server crash)
            error_4014 = MockConnectionClosed(4014)
            should_retry, needs_session = await self.voice_manager._handle_voice_connection_error(
                guild_id, error_4014
            )
            
            assert should_retry == True
            assert needs_session == False
            print("✅ Error 4014 triggers retry without new session")
            
        finally:
            # Restore original
            sys.modules['discord'].ConnectionClosed = original
        
    def test_health_status(self):
        """Test health status reporting"""
        print("\n📊 Testing Health Status...")
        
        # Set up some test states
        self.voice_manager.connection_states[1] = VoiceConnectionState.CONNECTED
        self.voice_manager.connection_states[2] = VoiceConnectionState.FAILED
        self.voice_manager.connection_states[3] = VoiceConnectionState.CONNECTING
        
        health = self.voice_manager.get_health_status()
        
        print(f"Environment: {health['environment']}")
        print(f"Total guilds: {health['total_guilds']}")
        print(f"Connected: {health['connected']}")
        print(f"Failed: {health['failed']}")
        print(f"Connection rate: {health['connection_rate']:.1%}")
        
        # The voice manager might have states from previous tests
        assert health['total_guilds'] >= 3
        assert health['connected'] >= 1
        assert health['failed'] >= 1
        print("✅ Health status correctly reports connection states")
        
    def run_all_tests(self):
        """Run all tests"""
        print("🧪 Running Voice Connection Manager Tests...")
        print("=" * 50)
        
        try:
            self.test_environment_detection()
            self.test_retry_delay_calculation()
            self.test_circuit_breaker()
            self.test_session_management()
            asyncio.run(self.test_error_handling())
            self.test_health_status()
            
            print("\n" + "=" * 50)
            print("✅ All tests passed!")
            print("\n📝 Summary:")
            print(f"- Environment: {self.voice_manager.environment.value}")
            print(f"- Max retries: {self.voice_manager.max_retry_attempts}")
            print(f"- Base delay: {self.voice_manager.base_retry_delay}s")
            print(f"- Connection timeout: {self.voice_manager.connection_timeout}s")
            print(f"- Circuit breaker threshold: {self.voice_manager.circuit_breaker_threshold}")
            
            if self.voice_manager.environment == DeploymentEnvironment.VPS:
                print("\n☁️ VPS optimizations are active:")
                print("- Extended timeouts for unstable networks")
                print("- Session recreation for error 4006")
                print("- Network stability checks enabled")
                print("- Higher circuit breaker threshold")
                
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    # Test with different environments
    if len(sys.argv) > 1 and sys.argv[1] in ['vps', 'local', 'docker']:
        print(f"🔧 Forcing {sys.argv[1].upper()} environment for testing...")
        os.environ['DEPLOYMENT_TYPE'] = sys.argv[1]
        # Also set IS_VPS for VPS detection
        if sys.argv[1] == 'vps':
            os.environ['IS_VPS'] = 'true'
        else:
            os.environ['IS_VPS'] = 'false'
            os.environ.pop('DISPLAY', None)  # Remove DISPLAY to simulate headless
    
    tester = TestVoiceConnectionManager()
    tester.run_all_tests()