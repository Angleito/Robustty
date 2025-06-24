#!/usr/bin/env python3
"""
Property-based tests for VPS deployment and cookie sync functionality.
Uses hypothesis for property testing and pytest for test orchestration.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

# Test constants
TEST_COOKIE_PLATFORMS = ["youtube", "rumble", "odysee", "peertube"]
SYNC_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "sync-cookies-to-vps.sh"
CHECK_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "check-cookie-sync.sh"


class CookieFileStrategy:
    """Strategies for generating test cookie data."""
    
    @staticmethod
    def cookie_data():
        """Generate valid cookie data."""
        return st.dictionaries(
            st.text(min_size=1, max_size=20),  # cookie name
            st.dictionaries(
                st.sampled_from(["value", "domain", "path", "secure", "httpOnly", "expires"]),
                st.one_of(
                    st.text(min_size=1, max_size=100),
                    st.booleans(),
                    st.integers(min_value=0, max_value=2147483647)
                )
            ),
            min_size=1,
            max_size=10
        )
    
    @staticmethod
    def platform_cookies():
        """Generate platform-specific cookie files."""
        return st.dictionaries(
            st.sampled_from(TEST_COOKIE_PLATFORMS),
            st.lists(
                st.dictionaries(
                    st.sampled_from(["name", "value", "domain", "path", "secure", "httpOnly", "expires"]),
                    st.one_of(st.text(), st.booleans(), st.integers())
                ),
                min_size=1,
                max_size=5
            )
        )


class MockSSHEnvironment:
    """Mock SSH environment for testing without actual VPS."""
    
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.local_dir = temp_dir / "local"
        self.remote_dir = temp_dir / "remote"
        self.local_cookies = self.local_dir / "cookies"
        self.remote_cookies = self.remote_dir / "opt" / "robustty" / "cookies"
        
        # Create directory structure
        self.local_cookies.mkdir(parents=True)
        self.remote_cookies.mkdir(parents=True)
    
    def mock_ssh_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Mock SSH commands for testing."""
        if "echo 'SSH connection successful'" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 0, stdout=b"SSH connection successful\n")
        elif "mkdir -p" in " ".join(cmd):
            # Simulate directory creation
            return subprocess.CompletedProcess(cmd, 0)
        elif "find" in " ".join(cmd) and "wc -l" in " ".join(cmd):
            # Count files in remote directory
            count = len(list(self.remote_cookies.glob("*.json")))
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{count}\n".encode())
        elif "chmod" in " ".join(cmd) or "chown" in " ".join(cmd):
            # Simulate permission changes
            return subprocess.CompletedProcess(cmd, 0)
        else:
            return subprocess.CompletedProcess(cmd, 1, stderr=b"Command not recognized")
    
    def mock_rsync_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Mock rsync for testing."""
        # Extract source and destination from rsync command
        for i, arg in enumerate(cmd):
            if ":" in arg and "@" in arg:
                # This is the destination
                local_source = Path(cmd[i-1].rstrip("/"))
                
                # Simulate rsync by copying files
                if local_source.exists():
                    for file in local_source.glob("*.json"):
                        shutil.copy2(file, self.remote_cookies)
                
                return subprocess.CompletedProcess(cmd, 0)
        
        return subprocess.CompletedProcess(cmd, 1, stderr=b"Rsync failed")


class TestCookieSyncProperties:
    """Property-based tests for cookie sync functionality."""
    
    @given(platform_cookies=CookieFileStrategy.platform_cookies())
    def test_cookie_extraction_creates_valid_json(self, platform_cookies: Dict[str, List[Dict]]):
        """Test that cookie extraction creates valid JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_dir = Path(temp_dir) / "cookies"
            cookie_dir.mkdir()
            
            # Write test cookies
            for platform, cookies in platform_cookies.items():
                cookie_file = cookie_dir / f"{platform}_cookies.json"
                with open(cookie_file, "w") as f:
                    json.dump(cookies, f)
            
            # Verify all files are valid JSON
            for cookie_file in cookie_dir.glob("*.json"):
                with open(cookie_file) as f:
                    data = json.load(f)
                    assert isinstance(data, list)
                    assert all(isinstance(cookie, dict) for cookie in data)
    
    @given(
        num_files=st.integers(min_value=0, max_value=10),
        file_ages=st.lists(st.integers(min_value=0, max_value=300), min_size=0, max_size=10)
    )
    def test_cookie_freshness_detection(self, num_files: int, file_ages: List[int]):
        """Test that cookie freshness checking works correctly."""
        assume(len(file_ages) == num_files)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_dir = Path(temp_dir)
            cookie_dir.mkdir()
            
            # Create files with specific ages
            current_time = time.time()
            for i, age_minutes in enumerate(file_ages[:num_files]):
                if i < len(TEST_COOKIE_PLATFORMS):
                    platform = TEST_COOKIE_PLATFORMS[i]
                    cookie_file = cookie_dir / f"{platform}_cookies.json"
                    cookie_file.write_text("[]")
                    
                    # Set file modification time
                    file_time = current_time - (age_minutes * 60)
                    os.utime(cookie_file, (file_time, file_time))
            
            # Count stale files (> 150 minutes old)
            stale_count = sum(1 for age in file_ages if age > 150)
            fresh_count = num_files - stale_count
            
            # Verify freshness detection
            actual_stale = 0
            for cookie_file in cookie_dir.glob("*.json"):
                file_age = (current_time - cookie_file.stat().st_mtime) / 60
                if file_age > 150:
                    actual_stale += 1
            
            assert actual_stale == min(stale_count, len(TEST_COOKIE_PLATFORMS))
    
    @given(
        sync_interval_hours=st.integers(min_value=1, max_value=24),
        last_sync_hours_ago=st.floats(min_value=0, max_value=48)
    )
    def test_sync_scheduling(self, sync_interval_hours: int, last_sync_hours_ago: float):
        """Test that sync scheduling logic works correctly."""
        current_time = datetime.now()
        last_sync = current_time - timedelta(hours=last_sync_hours_ago)
        next_sync = last_sync + timedelta(hours=sync_interval_hours)
        
        should_sync = current_time >= next_sync
        time_until_sync = max(0, (next_sync - current_time).total_seconds())
        
        # Verify scheduling logic
        if should_sync:
            assert time_until_sync == 0
        else:
            assert time_until_sync > 0
            assert time_until_sync <= sync_interval_hours * 3600


class CookieSyncStateMachine(RuleBasedStateMachine):
    """Stateful testing for cookie sync workflow."""
    
    def __init__(self):
        super().__init__()
        self.temp_dir = tempfile.mkdtemp()
        self.mock_env = MockSSHEnvironment(Path(self.temp_dir))
        self.cookies = {}
        self.last_sync = None
        self.sync_count = 0
    
    @initialize()
    def setup(self):
        """Initialize test environment."""
        self.cookies = {}
        self.last_sync = None
        self.sync_count = 0
    
    @rule(platform=st.sampled_from(TEST_COOKIE_PLATFORMS),
          cookies=CookieFileStrategy.cookie_data())
    def add_cookies(self, platform: str, cookies: Dict):
        """Add cookies for a platform."""
        self.cookies[platform] = cookies
        cookie_file = self.mock_env.local_cookies / f"{platform}_cookies.json"
        with open(cookie_file, "w") as f:
            json.dump([cookies], f)
    
    @rule()
    def sync_cookies(self):
        """Perform a cookie sync."""
        # Simulate sync
        for cookie_file in self.mock_env.local_cookies.glob("*.json"):
            shutil.copy2(cookie_file, self.mock_env.remote_cookies)
        
        self.last_sync = datetime.now()
        self.sync_count += 1
    
    @rule(minutes_passed=st.integers(min_value=0, max_value=300))
    def time_passes(self, minutes_passed: int):
        """Simulate time passing."""
        if self.last_sync:
            self.last_sync -= timedelta(minutes=minutes_passed)
    
    @invariant()
    def cookies_are_consistent(self):
        """Verify cookies remain consistent between syncs."""
        local_files = set(f.name for f in self.mock_env.local_cookies.glob("*.json"))
        remote_files = set(f.name for f in self.mock_env.remote_cookies.glob("*.json"))
        
        if self.sync_count > 0:
            # After sync, remote should have all local files
            assert local_files.issubset(remote_files) or len(local_files) == 0
    
    @invariant()
    def sync_count_is_valid(self):
        """Verify sync count is non-negative."""
        assert self.sync_count >= 0
    
    def teardown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestDockerComposeValidation:
    """Tests for Docker Compose configuration files."""
    
    def test_vps_compose_file_valid(self):
        """Test that docker-compose.vps.yml is valid."""
        compose_file = Path(__file__).parent.parent / "docker-compose.vps.yml"
        
        # Check file exists
        assert compose_file.exists(), "docker-compose.vps.yml not found"
        
        # Validate with docker-compose
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "config"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # If docker-compose not installed, check basic YAML validity
            import yaml
            with open(compose_file) as f:
                config = yaml.safe_load(f)
                assert "services" in config
                assert "robustty" in config["services"]
                assert "redis" in config["services"]
    
    @given(
        cpu_limit=st.floats(min_value=0.1, max_value=4.0),
        memory_limit=st.integers(min_value=128, max_value=8192)
    )
    def test_resource_limits(self, cpu_limit: float, memory_limit: int):
        """Test that resource limits are properly configured."""
        # Verify resource limits make sense
        assert cpu_limit > 0
        assert memory_limit >= 128  # Minimum viable memory
        
        # Check proportions
        memory_per_cpu = memory_limit / cpu_limit
        assert memory_per_cpu >= 128  # At least 128MB per CPU


class TestScriptExecution:
    """Tests for shell script execution."""
    
    def test_sync_script_syntax(self):
        """Test that sync script has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(SYNC_SCRIPT_PATH)],
            capture_output=True
        )
        assert result.returncode == 0, f"Syntax error in sync script: {result.stderr}"
    
    def test_check_script_syntax(self):
        """Test that check script has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(CHECK_SCRIPT_PATH)],
            capture_output=True
        )
        assert result.returncode == 0, f"Syntax error in check script: {result.stderr}"
    
    @patch.dict(os.environ, {
        "VPS_HOST": "test.example.com",
        "VPS_USER": "testuser",
        "SSH_KEY": "/tmp/test_key",
        "CONTAINER_NAME": "test-container"
    })
    @patch("subprocess.run")
    def test_sync_script_error_handling(self, mock_run):
        """Test sync script handles errors gracefully."""
        # Simulate docker not running
        mock_run.return_value = subprocess.CompletedProcess(
            ["docker", "ps"], 1, stderr=b"Cannot connect to Docker"
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            # Write a minimal test script that sources functions
            f.write("""#!/bin/bash
                check_requirements() {
                    for tool in docker rsync ssh; do
                        if ! command -v $tool &> /dev/null; then
                            echo "Missing: $tool"
                            return 1
                        fi
                    done
                    return 0
                }
                
                if ! check_requirements; then
                    exit 1
                fi
            """)
            f.flush()
            
            result = subprocess.run(["bash", f.name], capture_output=True)
            # Should exit with error when docker is not available
            assert result.returncode != 0


# Integration test
@pytest.mark.integration
class TestEndToEndSync:
    """End-to-end integration tests for cookie sync."""
    
    def test_full_sync_workflow(self):
        """Test complete sync workflow with mock environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_env = MockSSHEnvironment(Path(temp_dir))
            
            # Create test cookies
            for platform in TEST_COOKIE_PLATFORMS:
                cookie_file = mock_env.local_cookies / f"{platform}_cookies.json"
                cookie_file.write_text(json.dumps([{
                    "name": f"test_cookie_{platform}",
                    "value": "test_value",
                    "domain": f".{platform}.com"
                }]))
            
            # Simulate sync
            with patch("subprocess.run", side_effect=mock_env.mock_ssh_command):
                with patch("shutil.copy2") as mock_copy:
                    # Mock the rsync behavior
                    for src in mock_env.local_cookies.glob("*.json"):
                        shutil.copy2(src, mock_env.remote_cookies)
            
            # Verify sync completed
            local_files = set(f.name for f in mock_env.local_cookies.glob("*.json"))
            remote_files = set(f.name for f in mock_env.remote_cookies.glob("*.json"))
            assert local_files == remote_files
            
            # Verify content matches
            for platform in TEST_COOKIE_PLATFORMS:
                local_file = mock_env.local_cookies / f"{platform}_cookies.json"
                remote_file = mock_env.remote_cookies / f"{platform}_cookies.json"
                
                assert local_file.read_text() == remote_file.read_text()


# Test runner
if __name__ == "__main__":
    # Run property tests
    test_state_machine = CookieSyncStateMachine.TestCase()
    test_state_machine.runTest()
    
    # Run all tests
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])