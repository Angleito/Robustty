"""Tests for cross-platform cookie extraction"""
import pytest
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from src.extractors.browser_paths import detect_os, find_profiles, get_cookie_db_path
from src.extractors.cookie_database import Cookie, extract_sqlite_cookies, filter_expired_cookies
from src.extractors.cookie_decryption import decrypt_value
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor


class TestBrowserPaths:
    """Test browser path detection"""
    
    @patch('platform.system')
    def test_detect_os_windows(self, mock_system):
        """Test Windows OS detection"""
        mock_system.return_value = 'Windows'
        assert detect_os() == 'windows'
    
    @patch('platform.system')
    def test_detect_os_macos(self, mock_system):
        """Test macOS detection"""
        mock_system.return_value = 'Darwin'
        assert detect_os() == 'macos'
    
    @patch('platform.system')
    def test_detect_os_linux(self, mock_system):
        """Test Linux detection"""
        mock_system.return_value = 'Linux'
        assert detect_os() == 'linux'
    
    @patch('platform.system')
    def test_detect_os_unsupported(self, mock_system):
        """Test unsupported OS"""
        mock_system.return_value = 'UnknownOS'
        with pytest.raises(NotImplementedError):
            detect_os()
    
    @patch('src.extractors.browser_paths.Path.exists')
    @patch('src.extractors.browser_paths.Path.glob')
    def test_find_profiles_chrome(self, mock_glob, mock_exists):
        """Test finding Chrome profiles"""
        mock_exists.return_value = True
        mock_glob.return_value = [Path('Profile 1'), Path('Profile 2')]
        
        with patch('src.extractors.browser_paths.get_browser_paths') as mock_paths:
            mock_paths.return_value = {
                'chrome': {
                    'profiles_dir': Path('/test/chrome'),
                    'cookie_file': 'Cookies'
                }
            }
            
            profiles = find_profiles('chrome')
            assert len(profiles) > 0
    
    def test_get_cookie_db_path(self):
        """Test getting cookie database path"""
        with patch('src.extractors.browser_paths.get_browser_paths') as mock_paths:
            mock_paths.return_value = {
                'chrome': {
                    'profiles_dir': Path('/test/chrome'),
                    'cookie_file': 'Cookies'
                }
            }
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = True
                path = get_cookie_db_path('chrome', Path('/test/chrome/Default'))
                assert path == Path('/test/chrome/Default/Cookies')


class TestCookieDatabase:
    """Test SQLite cookie extraction"""
    
    def create_test_firefox_db(self, db_path: Path):
        """Create test Firefox cookie database"""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE moz_cookies (
                host TEXT,
                name TEXT,
                value TEXT,
                path TEXT,
                expiry INTEGER,
                isSecure INTEGER,
                isHttpOnly INTEGER
            )
        """)
        
        cursor.execute("""
            INSERT INTO moz_cookies VALUES
            ('example.com', 'test_cookie', 'test_value', '/', 9999999999, 1, 1)
        """)
        
        conn.commit()
        conn.close()
    
    def create_test_chrome_db(self, db_path: Path):
        """Create test Chrome cookie database"""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE cookies (
                host_key TEXT,
                name TEXT,
                value TEXT,
                encrypted_value BLOB,
                path TEXT,
                expires_utc INTEGER,
                is_secure INTEGER,
                is_httponly INTEGER
            )
        """)
        
        cursor.execute("""
            INSERT INTO cookies VALUES
            ('example.com', 'test_cookie', 'test_value', NULL, '/', 13300000000000000, 1, 1)
        """)
        
        conn.commit()
        conn.close()
    
    def test_extract_firefox_cookies(self):
        """Test extracting Firefox cookies"""
        # Create temp file with Firefox identifier in filename
        with tempfile.NamedTemporaryFile(suffix='_firefox_cookies.sqlite') as tmp:
            db_path = Path(tmp.name)
            self.create_test_firefox_db(db_path)
            
            cookies = extract_sqlite_cookies(db_path)
            
            assert len(cookies) == 1
            assert cookies[0].name == 'test_cookie'
            assert cookies[0].value == 'test_value'
    
    def test_extract_chrome_cookies(self):
        """Test extracting Chrome cookies"""
        with tempfile.NamedTemporaryFile(suffix='.sqlite') as tmp:
            db_path = Path(tmp.name)
            self.create_test_chrome_db(db_path)
            
            with patch('pathlib.Path.as_posix') as mock_posix:
                mock_posix.return_value = '/path/to/Chrome/Cookies'  # Mock Chrome detection
                cookies = extract_sqlite_cookies(db_path)
                
                assert len(cookies) == 1
                assert cookies[0].name == 'test_cookie'
                assert cookies[0].value == 'test_value'
    
    def test_filter_expired_cookies(self):
        """Test filtering expired cookies"""
        cookies = [
            Cookie(
                host_key='example.com',
                name='expired',
                value='value',
                path='/',
                expires_utc=1,  # Expired
                is_secure=False,
                is_httponly=False
            ),
            Cookie(
                host_key='example.com',
                name='valid',
                value='value',
                path='/',
                expires_utc=9999999999,  # Future
                is_secure=False,
                is_httponly=False
            )
        ]
        
        filtered = filter_expired_cookies(cookies)
        assert len(filtered) == 1
        assert filtered[0].name == 'valid'


class TestCookieDecryption:
    """Test platform-specific decryption"""
    
    @patch('src.extractors.browser_paths.detect_os')
    def test_decrypt_value_routing(self, mock_detect_os):
        """Test decryption routing based on OS"""
        mock_detect_os.return_value = 'windows'
        
        with patch('src.extractors.cookie_decryption.decrypt_windows') as mock_decrypt:
            mock_decrypt.return_value = 'decrypted'
            result = decrypt_value(b'encrypted', 'chrome')
            assert result == 'decrypted'
            mock_decrypt.assert_called_once()
    
    @patch('subprocess.run')
    def test_macos_keychain_access(self, mock_run):
        """Test macOS keychain access"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='base64encodedkey'
        )
        
        from src.extractors.cookie_decryption import get_keychain_key
        key = get_keychain_key('chrome')
        assert key is not None


class TestCrossPlatformCookieExtractor:
    """Test the unified cookie extractor"""
    
    @patch('src.extractors.cross_platform_cookies.find_profiles')
    @patch('src.extractors.cross_platform_cookies.extract_sqlite_cookies')
    def test_extract_all_cookies(self, mock_extract, mock_find):
        """Test extracting cookies from all browsers"""
        mock_find.return_value = [Path('/test/profile')]
        mock_extract.return_value = [
            Cookie(
                host_key='example.com',
                name='test',
                value='value',
                path='/',
                expires_utc=None,
                is_secure=False,
                is_httponly=False
            )
        ]
        
        with patch('src.extractors.cross_platform_cookies.get_cookie_db_path') as mock_path:
            mock_path.return_value = Path('/test/cookies.db')
            
            extractor = CrossPlatformCookieExtractor(['chrome'])
            cookies = extractor.extract_all_cookies()
            
            assert 'chrome' in cookies
            assert len(cookies['chrome']) == 1
    
    def test_load_all_cookies(self):
        """Test loading cookies into unified jar"""
        extractor = CrossPlatformCookieExtractor()
        
        with patch.object(extractor, 'extract_all_cookies') as mock_extract:
            mock_extract.return_value = {
                'chrome': [
                    Cookie(
                        host_key='example.com',
                        name='test',
                        value='value',
                        path='/',
                        expires_utc=None,
                        is_secure=False,
                        is_httponly=False
                    )
                ]
            }
            
            jar = extractor.load_all_cookies()
            assert len(jar) == 1
    
    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_save_cookies_json(self, mock_dump, mock_open):
        """Test saving cookies to JSON"""
        extractor = CrossPlatformCookieExtractor()
        
        with patch.object(extractor, 'extract_all_cookies') as mock_extract:
            mock_extract.return_value = {
                'chrome': [
                    Cookie(
                        host_key='example.com',
                        name='test',
                        value='value',
                        path='/',
                        expires_utc=None,
                        is_secure=False,
                        is_httponly=False
                    )
                ]
            }
            
            output_path = Path('/test/output.json')
            # Mock the mkdir call
            with patch('pathlib.Path.mkdir'):
                extractor.save_cookies_json(output_path)
            
            mock_dump.assert_called_once()
    
    def test_find_youtube_cookies(self):
        """Test finding YouTube-specific cookies"""
        extractor = CrossPlatformCookieExtractor()
        
        with patch.object(extractor, 'load_all_cookies') as mock_load:
            mock_load.return_value = Mock()
            extractor.find_youtube_cookies()
            
            mock_load.assert_called_once_with(
                domains=['youtube.com', '.youtube.com', 'www.youtube.com']
            )
    
    def test_find_platform_cookies(self):
        """Test finding platform-specific cookies"""
        extractor = CrossPlatformCookieExtractor()
        
        with patch.object(extractor, 'load_all_cookies') as mock_load:
            mock_load.return_value = Mock()
            
            # Test known platform
            extractor.find_platform_cookies('youtube')
            mock_load.assert_called_with(domains=['youtube.com', '.youtube.com'])
            
            # Test unknown platform
            jar = extractor.find_platform_cookies('unknown')
            assert len(jar) == 0