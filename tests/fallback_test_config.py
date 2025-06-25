"""
Configuration for fallback functionality tests

This module provides test configuration and utilities for testing
the YouTube platform fallback functionality.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Test environment configuration
TEST_CONFIG = {
    "youtube": {
        "enabled": True,
        "api_key": os.getenv("YOUTUBE_API_KEY", "test_api_key_for_testing"),
        "enable_fallbacks": True,
    },
    "fallback_manager": {
        "enable_fallbacks": True,
        "max_fallback_duration_hours": 1,  # Shorter for testing
        "retry_interval_minutes": 1,       # Faster for testing
    },
    "test_settings": {
        "mock_external_apis": True,
        "use_real_cookies": False,
        "timeout_seconds": 30,
        "max_retries": 3,
    }
}

# Sample test data
SAMPLE_YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ", 
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
    "Watch this video: https://www.youtube.com/watch?v=dQw4w9WgXcQ amazing!",
]

SAMPLE_VIDEO_METADATA = {
    "id": "dQw4w9WgXcQ",
    "title": "Never Gonna Give You Up",
    "channel": "Rick Astley",
    "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "platform": "youtube",
    "description": "The official video for Rick Astley's classic hit",
    "duration": "3:33",
    "views": "1.2B views",
    "published": "13 years ago",
    "view_count_raw": 1200000000,
}

SAMPLE_COOKIES = [
    {
        "name": "VISITOR_INFO1_LIVE",
        "value": "test_visitor_info_value",
        "domain": ".youtube.com",
        "path": "/",
        "secure": True,
        "expires": 1735689600  # 2025-01-01
    },
    {
        "name": "YSC",
        "value": "test_ysc_value",
        "domain": ".youtube.com", 
        "path": "/",
        "secure": True,
        "expires": 0
    },
    {
        "name": "CONSENT",
        "value": "YES+cb.20210420-17-p0.en+FX+123",
        "domain": ".youtube.com",
        "path": "/",
        "secure": True,
        "expires": 1735689600
    }
]

# Test scenarios for comprehensive testing
TEST_SCENARIOS = {
    "direct_url_processing": {
        "description": "Test direct YouTube URL processing",
        "test_urls": SAMPLE_YOUTUBE_URLS,
        "expected_video_id": "dQw4w9WgXcQ",
        "should_bypass_api": True,
    },
    "api_quota_exceeded": {
        "description": "Test behavior when API quota is exceeded",
        "simulate_quota_error": True,
        "expected_fallback_mode": "API_ONLY",
        "should_activate_fallback": True,
    },
    "cookie_authentication": {
        "description": "Test cookie-enhanced authentication",
        "use_mock_cookies": True,
        "test_cookie_conversion": True,
        "test_cookie_fallback": True,
    },
    "graceful_degradation": {
        "description": "Test graceful degradation when methods fail",
        "simulate_failures": ["yt_dlp_error", "network_error", "invalid_response"],
        "should_handle_gracefully": True,
    },
    "user_feedback": {
        "description": "Test user feedback and status reporting",
        "test_error_messages": True,
        "test_recommendations": True,
        "test_status_reporting": True,
    }
}

# Error simulation scenarios
ERROR_SCENARIOS = {
    "quota_exceeded": {
        "error_type": "HttpError",
        "status_code": 403,
        "error_content": b'{"error": {"errors": [{"reason": "quotaExceeded"}]}}',
        "expected_exception": "PlatformRateLimitError",
    },
    "authentication_error": {
        "error_type": "HttpError", 
        "status_code": 401,
        "error_content": b'{"error": {"errors": [{"reason": "unauthorized"}]}}',
        "expected_exception": "PlatformAuthenticationError",
    },
    "rate_limit": {
        "error_type": "HttpError",
        "status_code": 429,
        "error_content": b'{"error": {"errors": [{"reason": "rateLimitExceeded"}]}}',
        "expected_exception": "PlatformRateLimitError",
    },
    "service_unavailable": {
        "error_type": "HttpError",
        "status_code": 503,
        "error_content": b'Service Temporarily Unavailable',
        "expected_exception": "PlatformAPIError",
    },
    "video_private": {
        "error_type": "yt_dlp.DownloadError",
        "error_message": "This video is private",
        "expected_behavior": "return_error_message",
    },
    "video_unavailable": {
        "error_type": "yt_dlp.DownloadError", 
        "error_message": "Video unavailable",
        "expected_behavior": "return_error_message",
    },
    "copyright_blocked": {
        "error_type": "yt_dlp.DownloadError",
        "error_message": "Video blocked due to copyright claim",
        "expected_behavior": "return_error_message",
    },
    "region_blocked": {
        "error_type": "yt_dlp.DownloadError",
        "error_message": "Video not available in your region",
        "expected_behavior": "return_error_message",
    }
}

# Test markers for pytest
TEST_MARKERS = {
    "unit": "Unit tests that don't require external services",
    "integration": "Integration tests that may require external APIs",
    "slow": "Tests that take longer to run",
    "api_dependent": "Tests that require real API access",
    "cookie_dependent": "Tests that require cookie files",
}


def get_test_config() -> Dict[str, Any]:
    """Get the complete test configuration"""
    return TEST_CONFIG.copy()


def get_mock_cookie_file_content() -> str:
    """Get mock cookie file content as JSON string"""
    import json
    return json.dumps(SAMPLE_COOKIES, indent=2)


def get_mock_netscape_cookie_content() -> str:
    """Get mock Netscape cookie file content"""
    lines = [
        "# Netscape HTTP Cookie File",
        "# This is a generated file! Do not edit.",
        "",
    ]
    
    for cookie in SAMPLE_COOKIES:
        domain = cookie["domain"]
        domain_flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie["path"]
        secure = "TRUE" if cookie["secure"] else "FALSE"
        expires = str(cookie["expires"])
        name = cookie["name"]
        value = cookie["value"]
        
        line = f"{domain}\t{domain_flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}"
        lines.append(line)
    
    return "\n".join(lines)


def validate_test_prerequisites() -> bool:
    """Validate that test prerequisites are met"""
    try:
        # Check required imports
        import pytest
        import src.platforms.youtube
        import src.services.platform_fallback_manager
        
        # Check test files exist
        test_files = [
            "tests/test_platforms/test_youtube_fallback_comprehensive.py",
            "tests/test_services/test_platform_fallback_manager.py",
            "tests/integration/test_youtube_fallback_integration.py",
        ]
        
        missing_files = []
        for test_file in test_files:
            if not Path(test_file).exists():
                missing_files.append(test_file)
        
        if missing_files:
            print(f"Missing test files: {missing_files}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        return False


def get_test_summary() -> str:
    """Get a summary of available tests"""
    return """
YouTube Platform Fallback Test Suite
====================================

Test Categories:
1. Direct URL Processing Tests
   - URL pattern recognition
   - Video ID extraction
   - Metadata retrieval via yt-dlp
   - Bypassing API for URL-based queries

2. API Quota Fallback Tests
   - Quota exceeded detection
   - Automatic fallback activation
   - yt-dlp search fallback
   - Error handling and reporting

3. Cookie Authentication Tests
   - Cookie file detection and loading
   - JSON to Netscape format conversion
   - Cookie-enhanced stream extraction
   - Fallback paths for missing cookies

4. Graceful Degradation Tests
   - Multiple failure scenario handling
   - Format fallback for stream extraction
   - Partial recovery scenarios
   - Error message clarity

5. Fallback Manager Tests
   - Strategy selection and activation
   - Operation restrictions by mode
   - User recommendations
   - History tracking and reporting

6. Integration Tests
   - End-to-end fallback workflows
   - Component integration
   - Real-world scenario simulation
   - Performance characteristics

Running Tests:
- Use: python tests/run_fallback_tests.py
- For specific scenarios: python tests/run_fallback_tests.py --scenarios url_processing api_quota
- For integration tests: python tests/run_fallback_tests.py --include-integration

Test Markers:
- @pytest.mark.unit: Unit tests
- @pytest.mark.integration: Integration tests
- @pytest.mark.asyncio: Async tests
"""


if __name__ == "__main__":
    print(get_test_summary())
    print("\nValidating test prerequisites...")
    if validate_test_prerequisites():
        print("✅ All prerequisites met!")
    else:
        print("❌ Prerequisites not met")