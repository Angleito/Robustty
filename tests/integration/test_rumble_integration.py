"""Integration tests for Rumble platform with real Apify API calls."""

import os
import pytest
import logging
from unittest.mock import patch, Mock
from datetime import datetime

from src.platforms.rumble import RumblePlatform
from src.platforms.errors import PlatformNotAvailableError, VideoNotFoundError, RateLimitError
from src.services.apify_auth import ApifyAuthError


logger = logging.getLogger(__name__)


# Skip these tests if no Apify API key is provided
pytestmark = pytest.mark.skipif(
    not os.environ.get('APIFY_API_KEY'),
    reason="APIFY_API_KEY environment variable not set"
)


@pytest.fixture
def rumble_platform():
    """Create RumblePlatform instance with real API key."""
    platform = RumblePlatform()
    platform.config = {
        'enabled': True,
        'max_results': 10
    }
    return platform


@pytest.mark.integration
@pytest.mark.slow
class TestRumbleIntegration:
    """Integration tests that make real API calls to Apify/Rumble."""

    @pytest.fixture(autouse=True)
    def setup(self, caplog):
        """Setup for each test."""
        caplog.set_level(logging.INFO)
        yield
        # Allow time between tests to avoid rate limiting
        import time
        time.sleep(1)

    def test_real_rumble_search(self, rumble_platform):
        """Test search with actual Rumble content."""
        # Search for a popular, stable query
        results = rumble_platform.search("gaming", limit=5)
        
        assert len(results) <= 5
        for result in results:
            assert result.video_id
            assert result.title
            assert result.platform == 'rumble'
            assert result.url.startswith('https://rumble.com/')
            assert result.duration > 0
            assert result.views >= 0
            assert result.uploaded_at is not None

    def test_real_video_metadata(self, rumble_platform):
        """Test video metadata extraction with real video."""
        # Use a known stable video ID for testing
        # This should be updated if the video becomes unavailable
        test_video_url = "https://rumble.com/v1o9t7f-test-video.html"
        
        try:
            result = rumble_platform.get_video_info(test_video_url)
            
            assert result.video_id
            assert result.title
            assert result.description
            assert result.platform == 'rumble'
            assert result.url == test_video_url
            assert result.duration > 0
            assert result.views >= 0
            assert result.uploaded_at is not None
            
            # Verify uploader info
            assert result.uploader
            assert result.uploader_url
            
            # Verify thumbnails
            assert result.thumbnails
            assert len(result.thumbnails) > 0
            assert all(t.url for t in result.thumbnails)
            
        except VideoNotFoundError:
            pytest.skip("Test video no longer available")

    def test_real_stream_extraction(self, rumble_platform):
        """Test stream URL extraction with real video."""
        test_video_url = "https://rumble.com/v1o9t7f-test-video.html"
        
        try:
            streams = rumble_platform.get_streams(test_video_url)
            
            assert streams
            assert 'best' in streams
            assert 'audio' in streams
            
            # Verify best stream
            best_stream = streams['best']
            assert best_stream.url
            assert best_stream.format_id
            assert best_stream.quality
            assert best_stream.container
            
            # Verify audio stream
            audio_stream = streams['audio']
            assert audio_stream.url
            assert audio_stream.format_id
            assert 'audio' in audio_stream.quality.lower()
            
        except VideoNotFoundError:
            pytest.skip("Test video no longer available")

    def test_rate_limit_handling(self, rumble_platform):
        """Test rate limiting behavior with multiple rapid requests."""
        # Make multiple rapid requests to trigger rate limiting
        successful_requests = 0
        rate_limited = False
        
        for i in range(10):
            try:
                results = rumble_platform.search(f"test query {i}", limit=3)
                successful_requests += 1
            except RateLimitError:
                rate_limited = True
                break
            except Exception as e:
                # Log unexpected errors but continue
                logger.warning(f"Unexpected error during rate limit test: {e}")
                
        # We expect some requests to succeed before hitting rate limit
        assert successful_requests > 0
        
        # Note: We might not hit rate limits in testing, which is fine
        if rate_limited:
            logger.info("Rate limit was triggered as expected")

    def test_error_scenarios(self, rumble_platform):
        """Test various error scenarios with real API."""
        # Test invalid video URL
        with pytest.raises(VideoNotFoundError):
            rumble_platform.get_video_info("https://rumble.com/v-invalid-video.html")
        
        # Test empty search query
        results = rumble_platform.search("", limit=5)
        assert results == []
        
        # Test special characters in search
        results = rumble_platform.search("test @#$%", limit=3)
        # Should handle special characters gracefully
        assert isinstance(results, list)
        
        # Test extremely long query
        long_query = "a" * 500
        results = rumble_platform.search(long_query, limit=3)
        assert isinstance(results, list)

    def test_search_pagination(self, rumble_platform):
        """Test search with different limit values."""
        # Test small limit
        results_small = rumble_platform.search("music", limit=3)
        assert len(results_small) <= 3
        
        # Test larger limit
        results_large = rumble_platform.search("music", limit=10)
        assert len(results_large) <= 10
        
        # Results should have consistent structure
        if results_large:
            first_result = results_large[0]
            assert hasattr(first_result, 'video_id')
            assert hasattr(first_result, 'title')
            assert hasattr(first_result, 'duration')

    @pytest.mark.parametrize("query,expected_min_results", [
        ("news", 1),      # Popular category
        ("sports", 1),    # Popular category
        ("tutorial", 1),  # Common content type
    ])
    def test_category_searches(self, rumble_platform, query, expected_min_results):
        """Test searches for common categories."""
        results = rumble_platform.search(query, limit=5)
        
        assert len(results) >= expected_min_results
        
        # All results should be from Rumble
        for result in results:
            assert result.platform == 'rumble'
            assert query.lower() in result.title.lower() or query.lower() in result.description.lower()

    def test_invalid_api_key_handling(self):
        """Test behavior with invalid API key."""
        with patch.dict(os.environ, {'APIFY_API_KEY': 'invalid_key_12345'}):
            platform = RumblePlatform()
            platform.config = {'enabled': True}
            
            with pytest.raises((PlatformNotAvailableError, ApifyAuthError)):
                platform.search("test", limit=5)


class TestRumbleIntegrationWithMocks:
    """Tests that simulate integration scenarios using mocks."""
    
    def test_network_timeout_handling(self, rumble_platform):
        """Test handling of network timeouts."""
        with patch('src.services.apify_client.httpx.Client.request') as mock_request:
            import httpx
            mock_request.side_effect = httpx.TimeoutException("Request timed out")
            
            with pytest.raises((PlatformNotAvailableError, Exception)):
                rumble_platform.search("test", limit=5)

    def test_malformed_response_handling(self, rumble_platform):
        """Test handling of malformed API responses."""
        with patch('src.services.apify_client.ApifyClient.get_datasets') as mock_get:
            # Return malformed data
            mock_get.return_value = [
                {
                    'id': '123',
                    'fields': {
                        # Missing required fields
                        'title': 'Test Video'
                    }
                }
            ]
            
            results = rumble_platform.search("test", limit=5)
            # Should handle gracefully and return empty or skip malformed entries
            assert isinstance(results, list)

    def test_concurrent_request_handling(self, rumble_platform):
        """Test handling of concurrent requests."""
        import concurrent.futures
        
        def make_search(query):
            return rumble_platform.search(query, limit=3)
        
        queries = ["test1", "test2", "test3"]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_search, q) for q in queries]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All requests should complete successfully
        assert len(results) == 3
        for result in results:
            assert isinstance(result, list)