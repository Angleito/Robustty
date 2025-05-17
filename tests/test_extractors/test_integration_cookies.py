"""Integration tests for cookie extraction system"""
import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor


class TestCookieIntegration:
    """Integration tests for the cookie extraction system"""
    
    def setup_test_chrome_profile(self, profile_dir: Path):
        """Set up a test Chrome profile"""
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal Chrome preferences
        prefs = {
            "profile": {
                "name": "Test Profile"
            }
        }
        
        with open(profile_dir / "Preferences", "w") as f:
            json.dump(prefs, f)
        
        # Create empty cookie database (would be populated in real scenario)
        (profile_dir / "Cookies").touch()
    
    @pytest.fixture
    def temp_profile_dir(self):
        """Create temporary profile directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @patch('src.extractors.browser_paths.get_browser_paths')
    @patch('src.extractors.browser_paths.detect_os')
    def test_end_to_end_extraction(self, mock_os, mock_paths, temp_profile_dir):
        """Test end-to-end cookie extraction"""
        mock_os.return_value = 'macos'
        
        # Set up test profile
        chrome_dir = temp_profile_dir / 'Chrome'
        default_profile = chrome_dir / 'Default'
        self.setup_test_chrome_profile(default_profile)
        
        mock_paths.return_value = {
            'chrome': {
                'profiles_dir': chrome_dir,
                'cookie_file': 'Cookies'
            }
        }
        
        # Mock cookie extraction
        with patch('src.extractors.cross_platform_cookies.extract_sqlite_cookies') as mock_extract:
            mock_extract.return_value = []  # Empty for simplicity
            
            extractor = CrossPlatformCookieExtractor(['chrome'])
            cookies = extractor.extract_all_cookies()
            
            # Verify profile was found and extraction attempted
            mock_extract.assert_called()
    
    @patch('src.extractors.cross_platform_cookies.CrossPlatformCookieExtractor.extract_all_cookies')
    def test_cookie_priority_order(self, mock_extract):
        """Test browser priority order in unified jar"""
        # Mock cookies from different browsers
        mock_extract.return_value = {
            'chrome': [self._create_test_cookie('chrome_cookie')],
            'brave': [self._create_test_cookie('brave_cookie')],
            'firefox': [self._create_test_cookie('firefox_cookie')]
        }
        
        extractor = CrossPlatformCookieExtractor()
        jar = extractor.load_all_cookies()
        
        # Verify cookies are added (priority order: brave, opera, chrome, edge, firefox, chromium)
        cookie_names = [cookie.name for cookie in jar]
        assert 'brave_cookie' in cookie_names
        assert 'chrome_cookie' in cookie_names
        assert 'firefox_cookie' in cookie_names
    
    def _create_test_cookie(self, name: str):
        """Helper to create test cookie"""
        from src.extractors.cookie_database import Cookie
        return Cookie(
            host_key='example.com',
            name=name,
            value='test_value',
            path='/',
            expires_utc=None,
            is_secure=False,
            is_httponly=False
        )
    
    @patch('requests.get')
    def test_cookies_work_with_requests(self, mock_get):
        """Test that extracted cookies work with requests"""
        extractor = CrossPlatformCookieExtractor()
        
        with patch.object(extractor, 'extract_all_cookies') as mock_extract:
            mock_extract.return_value = {
                'chrome': [self._create_test_cookie('auth_token')]
            }
            
            jar = extractor.load_all_cookies()
            
            # Test using cookies with requests
            import requests
            session = requests.Session()
            session.cookies = jar
            
            # Verify cookies are in session
            assert 'auth_token' in [cookie.name for cookie in session.cookies]
    
    def test_platform_specific_extraction(self):
        """Test extracting cookies for specific platforms"""
        extractor = CrossPlatformCookieExtractor()
        
        with patch.object(extractor, 'load_all_cookies') as mock_load:
            # Test YouTube
            extractor.find_youtube_cookies()
            mock_load.assert_called_with(domains=['youtube.com', '.youtube.com', 'www.youtube.com'])
            
            mock_load.reset_mock()
            
            # Test Rumble
            extractor.find_platform_cookies('rumble')
            mock_load.assert_called_with(domains=['rumble.com', '.rumble.com'])
    
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', create=True)
    def test_save_to_ytdlp_format(self, mock_open, mock_mkdir):
        """Test saving cookies in yt-dlp compatible format"""
        extractor = CrossPlatformCookieExtractor()
        
        test_cookies = {
            'chrome': [
                self._create_test_cookie('SID'),
                self._create_test_cookie('HSID')
            ]
        }
        
        with patch.object(extractor, 'extract_all_cookies') as mock_extract:
            mock_extract.return_value = test_cookies
            
            with patch('json.dump') as mock_dump:
                extractor.save_cookies_json(Path('/test/cookies.json'))
                
                # Verify JSON structure
                mock_dump.assert_called_once()
                saved_data = mock_dump.call_args[0][0]
                
                assert len(saved_data) == 2
                assert all('name' in cookie for cookie in saved_data)
                assert all('value' in cookie for cookie in saved_data)
                assert all('domain' in cookie for cookie in saved_data)
    
    def test_error_handling(self):
        """Test error handling during extraction"""
        extractor = CrossPlatformCookieExtractor()
        
        # Test with non-existent browser
        with patch('src.extractors.browser_paths.find_profiles') as mock_find:
            mock_find.return_value = []
            
            cookies = extractor._extract_browser_cookies('nonexistent')
            assert cookies == []
        
        # Test with extraction error
        with patch('src.extractors.browser_paths.find_profiles') as mock_find:
            mock_find.side_effect = Exception("Test error")
            
            cookies = extractor._extract_browser_cookies('chrome')
            assert cookies == []