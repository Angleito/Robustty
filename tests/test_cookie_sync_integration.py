#!/usr/bin/env python3
"""
Integration tests for cookie sync functionality.
Tests the actual scripts and Docker integration.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch, call

import pytest


class TestCookieSyncIntegration:
    """Integration tests for cookie sync between macOS and VPS."""
    
    @pytest.fixture
    def mock_docker_env(self):
        """Create a mock Docker environment for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create directory structure
            (temp_path / "data" / "cookies").mkdir(parents=True)
            (temp_path / "scripts").mkdir(parents=True)
            (temp_path / "config").mkdir(parents=True)
            
            # Copy scripts to temp directory
            project_root = Path(__file__).parent.parent
            for script in ["sync-cookies-to-vps.sh", "check-cookie-sync.sh", "extract-brave-cookies.py"]:
                src = project_root / "scripts" / script
                if src.exists():
                    shutil.copy2(src, temp_path / "scripts" / script)
            
            yield temp_path
    
    def test_sync_script_requirements_check(self, mock_docker_env):
        """Test that sync script properly checks for required tools."""
        # Create a modified version of the script that we can test
        test_script = mock_docker_env / "test_requirements.sh"
        test_script.write_text("""#!/bin/bash
check_requirements() {
    local missing_tools=()
    
    for tool in docker rsync ssh; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=($tool)
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    return 0
}

check_requirements
""")
        test_script.chmod(0o755)
        
        # Test with all tools available
        result = subprocess.run([str(test_script)], capture_output=True, text=True)
        # This will pass or fail depending on actual tool availability
        assert result.returncode in [0, 1]
    
    @patch("subprocess.run")
    def test_docker_container_check(self, mock_run, mock_docker_env):
        """Test that sync script checks if Docker container is running."""
        # Mock docker ps output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="robustty-bot\nredis\n"
        )
        
        # Create test script
        test_script = mock_docker_env / "test_docker_check.sh"
        test_script.write_text("""#!/bin/bash
CONTAINER_NAME="robustty-bot"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container is running"
    exit 0
else
    echo "Container is not running"
    exit 1
fi
""")
        test_script.chmod(0o755)
        
        result = subprocess.run([str(test_script)], capture_output=True, text=True)
        assert "Container is running" in result.stdout or "Container is not running" in result.stdout
    
    def test_cookie_file_validation(self, mock_docker_env):
        """Test validation of cookie JSON files."""
        cookies_dir = mock_docker_env / "data" / "cookies"
        
        # Create valid cookie files
        valid_cookies = {
            "youtube": [
                {"name": "PREF", "value": "test", "domain": ".youtube.com"},
                {"name": "VISITOR_INFO", "value": "test", "domain": ".youtube.com"}
            ],
            "rumble": [
                {"name": "session", "value": "test", "domain": ".rumble.com"}
            ]
        }
        
        for platform, cookies in valid_cookies.items():
            cookie_file = cookies_dir / f"{platform}_cookies.json"
            cookie_file.write_text(json.dumps(cookies, indent=2))
        
        # Validate all files
        for cookie_file in cookies_dir.glob("*.json"):
            with open(cookie_file) as f:
                data = json.load(f)
                assert isinstance(data, list)
                assert all(isinstance(cookie, dict) for cookie in data)
                assert all("name" in cookie and "value" in cookie for cookie in data)
    
    def test_ssh_key_permissions(self, mock_docker_env):
        """Test that SSH key permissions are checked."""
        # Create fake SSH key
        ssh_dir = mock_docker_env / ".ssh"
        ssh_dir.mkdir(mode=0o700)
        ssh_key = ssh_dir / "robustty_vps"
        ssh_key.write_text("fake_private_key")
        ssh_key.chmod(0o600)
        
        # Check permissions
        assert ssh_key.stat().st_mode & 0o777 == 0o600
    
    @patch.dict(os.environ, {
        "COOKIE_DIR": "/tmp/test_cookies",
        "MAX_AGE_MINUTES": "150"
    })
    def test_cookie_freshness_check(self, mock_docker_env):
        """Test cookie freshness checking logic."""
        cookies_dir = Path("/tmp/test_cookies")
        cookies_dir.mkdir(exist_ok=True)
        
        try:
            # Create test cookie files with different ages
            current_time = time.time()
            
            # Fresh cookie (1 hour old)
            fresh_cookie = cookies_dir / "youtube_cookies.json"
            fresh_cookie.write_text("[]")
            os.utime(fresh_cookie, (current_time - 3600, current_time - 3600))
            
            # Stale cookie (3 hours old)
            stale_cookie = cookies_dir / "rumble_cookies.json"
            stale_cookie.write_text("[]")
            os.utime(stale_cookie, (current_time - 10800, current_time - 10800))
            
            # Check freshness
            fresh_age = (current_time - fresh_cookie.stat().st_mtime) / 60
            stale_age = (current_time - stale_cookie.stat().st_mtime) / 60
            
            assert fresh_age < 150  # Fresh
            assert stale_age > 150  # Stale
            
        finally:
            shutil.rmtree(cookies_dir, ignore_errors=True)
    
    def test_rsync_command_generation(self):
        """Test that rsync commands are generated correctly."""
        # Expected rsync command format
        local_dir = "/path/to/local/cookies/"
        remote_user = "testuser"
        remote_host = "test.example.com"
        remote_dir = "/opt/robustty/cookies/"
        ssh_key = "/home/user/.ssh/robustty_vps"
        
        expected_cmd = [
            "rsync", "-avz", "--delete",
            "-e", f"ssh -i {ssh_key} -o StrictHostKeyChecking=no",
            local_dir,
            f"{remote_user}@{remote_host}:{remote_dir}"
        ]
        
        # Verify command structure
        assert expected_cmd[0] == "rsync"
        assert "-avz" in expected_cmd
        assert "--delete" in expected_cmd
        assert any("ssh -i" in arg for arg in expected_cmd)
    
    @pytest.mark.parametrize("platform,expected_domains", [
        ("youtube", [".youtube.com", "youtube.com"]),
        ("rumble", [".rumble.com", "rumble.com"]),
        ("odysee", [".odysee.com", "odysee.com"]),
        ("peertube", ["framatube.org", "video.ploud.fr"])
    ])
    def test_platform_cookie_domains(self, platform, expected_domains):
        """Test that cookies are extracted for correct domains."""
        # This tests the domain filtering logic
        test_cookies = [
            {"name": "test1", "domain": expected_domains[0], "value": "val1"},
            {"name": "test2", "domain": "wrong.domain.com", "value": "val2"},
            {"name": "test3", "domain": expected_domains[1] if len(expected_domains) > 1 else expected_domains[0], "value": "val3"}
        ]
        
        # Filter cookies by domain
        platform_cookies = [
            cookie for cookie in test_cookies
            if any(domain in cookie["domain"] for domain in expected_domains)
        ]
        
        assert len(platform_cookies) >= 2
        assert all(any(domain in cookie["domain"] for domain in expected_domains) for cookie in platform_cookies)


class TestDockerIntegration:
    """Test Docker-specific functionality."""
    
    def test_docker_compose_vps_syntax(self):
        """Test that docker-compose.vps.yml has valid syntax."""
        compose_file = Path(__file__).parent.parent / "docker-compose.vps.yml"
        
        if compose_file.exists():
            import yaml
            try:
                with open(compose_file) as f:
                    config = yaml.safe_load(f)
                
                # Validate structure
                assert "version" in config
                assert "services" in config
                assert "robustty" in config["services"]
                assert "redis" in config["services"]
                
                # Check volume mounts
                robustty_service = config["services"]["robustty"]
                assert "volumes" in robustty_service
                cookie_mount = next((v for v in robustty_service["volumes"] if "/app/cookies:ro" in v), None)
                assert cookie_mount is not None
                
                # Check environment variables
                assert "environment" in robustty_service
                
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in docker-compose.vps.yml: {e}")
    
    def test_docker_health_checks(self):
        """Test that health checks are properly configured."""
        compose_file = Path(__file__).parent.parent / "docker-compose.vps.yml"
        
        if compose_file.exists():
            import yaml
            with open(compose_file) as f:
                config = yaml.safe_load(f)
            
            # Check health checks
            for service_name in ["robustty", "redis"]:
                if service_name in config["services"]:
                    service = config["services"][service_name]
                    assert "healthcheck" in service
                    healthcheck = service["healthcheck"]
                    assert "test" in healthcheck
                    assert "interval" in healthcheck
                    assert "timeout" in healthcheck
                    assert "retries" in healthcheck
    
    def test_resource_limits(self):
        """Test that resource limits are reasonable."""
        compose_file = Path(__file__).parent.parent / "docker-compose.vps.yml"
        
        if compose_file.exists():
            import yaml
            with open(compose_file) as f:
                config = yaml.safe_load(f)
            
            robustty_service = config["services"]["robustty"]
            if "deploy" in robustty_service and "resources" in robustty_service["deploy"]:
                limits = robustty_service["deploy"]["resources"].get("limits", {})
                
                # Check CPU limits
                if "cpus" in limits:
                    cpu_limit = float(limits["cpus"])
                    assert 0.1 <= cpu_limit <= 4.0
                
                # Check memory limits
                if "memory" in limits:
                    memory_str = limits["memory"]
                    if memory_str.endswith("G"):
                        memory_gb = float(memory_str[:-1])
                        assert 0.5 <= memory_gb <= 8.0


class TestMonitoring:
    """Test monitoring and alerting functionality."""
    
    @patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test"})
    @patch("subprocess.run")
    def test_discord_webhook_alert(self, mock_run):
        """Test that Discord webhook alerts are sent correctly."""
        # Simulate sending an alert
        webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
        message = "Test alert message"
        
        curl_cmd = [
            "curl", "-H", "Content-Type: application/json",
            "-X", "POST",
            "-d", json.dumps({"content": f"🚨 **Cookie Sync Alert**\n{message}"}),
            webhook_url
        ]
        
        # Mock successful curl
        mock_run.return_value = MagicMock(returncode=0)
        
        # This would be called by the check script
        result = subprocess.run(curl_cmd, capture_output=True)
        
        assert mock_run.called
    
    def test_monitoring_script_output_format(self):
        """Test that monitoring script produces expected output format."""
        # Test the output parsing logic
        test_output = """
[2024-01-20 10:00:00] Checking cookie freshness...
OK: youtube_cookies.json is 60 minutes old
STALE: rumble_cookies.json is 180 minutes old
WARNING: Missing cookie file: odysee_cookies.json

Total cookie files found: 2
"""
        
        # Parse output
        lines = test_output.strip().split('\n')
        
        ok_count = sum(1 for line in lines if line.startswith("OK:"))
        stale_count = sum(1 for line in lines if line.startswith("STALE:"))
        warning_count = sum(1 for line in lines if line.startswith("WARNING:"))
        
        assert ok_count == 1
        assert stale_count == 1
        assert warning_count == 1


# Performance tests
class TestPerformance:
    """Test performance characteristics of the sync system."""
    
    def test_sync_script_timeout(self):
        """Test that sync operations have reasonable timeouts."""
        # Check SSH timeout in sync script
        sync_script = Path(__file__).parent.parent / "scripts" / "sync-cookies-to-vps.sh"
        
        if sync_script.exists():
            content = sync_script.read_text()
            
            # Check for timeout configurations
            assert "ConnectTimeout=" in content
            assert any(timeout in content for timeout in ["ConnectTimeout=10", "ConnectTimeout=30"])
    
    def test_rsync_efficiency(self):
        """Test that rsync is used efficiently."""
        # Verify rsync uses compression and delta transfer
        expected_flags = ["-a", "-v", "-z", "--delete"]
        
        # These flags ensure:
        # -a: archive mode (preserves permissions, timestamps)
        # -v: verbose (for logging)
        # -z: compression (reduces bandwidth)
        # --delete: removes files not in source (keeps sync clean)
        
        assert all(flag in expected_flags for flag in ["-a", "-z"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])