"""Browser profile path detection across different operating systems"""
import platform
from pathlib import Path
from typing import Dict, List, Optional


def detect_os() -> str:
    """Detect the current operating system
    
    Returns:
        str: 'windows' or 'macos' or 'linux'
    """
    system = platform.system().lower()
    if system == 'darwin':
        return 'macos'
    elif system == 'windows':
        return 'windows'
    elif system == 'linux':
        return 'linux'
    else:
        raise NotImplementedError(f"Unsupported operating system: {system}")


def get_browser_paths() -> Dict[str, Dict[str, Path]]:
    """Get browser paths for the current OS
    
    Returns:
        Dict mapping browser names to their profile paths
    """
    os_name = detect_os()
    
    if os_name == 'windows':
        local_appdata = Path.home() / 'AppData' / 'Local'
        appdata = Path.home() / 'AppData' / 'Roaming'
        
        return {
            'chrome': {
                'profiles_dir': local_appdata / 'Google' / 'Chrome' / 'User Data',
                'cookie_file': 'Cookies'
            },
            'chromium': {
                'profiles_dir': local_appdata / 'Chromium' / 'User Data',
                'cookie_file': 'Cookies'
            },
            'edge': {
                'profiles_dir': local_appdata / 'Microsoft' / 'Edge' / 'User Data',
                'cookie_file': 'Cookies'
            },
            'brave': {
                'profiles_dir': local_appdata / 'BraveSoftware' / 'Brave-Browser' / 'User Data',
                'cookie_file': 'Cookies'
            },
            'opera': {
                'profiles_dir': appdata / 'Opera Software' / 'Opera Stable',
                'cookie_file': 'Cookies'
            },
            'firefox': {
                'profiles_dir': appdata / 'Mozilla' / 'Firefox' / 'Profiles',
                'cookie_file': 'cookies.sqlite'
            }
        }
    
    elif os_name == 'macos':
        app_support = Path.home() / 'Library' / 'Application Support'
        
        return {
            'chrome': {
                'profiles_dir': app_support / 'Google' / 'Chrome',
                'cookie_file': 'Cookies'
            },
            'chromium': {
                'profiles_dir': app_support / 'Chromium',
                'cookie_file': 'Cookies'
            },
            'edge': {
                'profiles_dir': app_support / 'Microsoft Edge',
                'cookie_file': 'Cookies'
            },
            'brave': {
                'profiles_dir': app_support / 'BraveSoftware' / 'Brave-Browser',
                'cookie_file': 'Cookies'
            },
            'opera': {
                'profiles_dir': app_support / 'com.operasoftware.Opera',
                'cookie_file': 'Cookies'
            },
            'firefox': {
                'profiles_dir': app_support / 'Firefox' / 'Profiles',
                'cookie_file': 'cookies.sqlite'
            }
        }
    
    elif os_name == 'linux':
        config_home = Path.home() / '.config'
        mozilla_dir = Path.home() / '.mozilla'
        
        return {
            'chrome': {
                'profiles_dir': config_home / 'google-chrome',
                'cookie_file': 'Cookies'
            },
            'chromium': {
                'profiles_dir': config_home / 'chromium',
                'cookie_file': 'Cookies'
            },
            'edge': {
                'profiles_dir': config_home / 'microsoft-edge',
                'cookie_file': 'Cookies'
            },
            'brave': {
                'profiles_dir': config_home / 'BraveSoftware' / 'Brave-Browser',
                'cookie_file': 'Cookies'
            },
            'opera': {
                'profiles_dir': config_home / 'opera',
                'cookie_file': 'Cookies'
            },
            'firefox': {
                'profiles_dir': mozilla_dir / 'firefox',
                'cookie_file': 'cookies.sqlite'
            }
        }
    
    else:
        raise NotImplementedError(f"Unsupported OS: {os_name}")


def find_profiles(browser: str) -> List[Path]:
    """Find all profiles for a specific browser
    
    Args:
        browser: Browser name ('chrome', 'firefox', etc.)
        
    Returns:
        List of profile directories
    """
    browser_paths = get_browser_paths()
    
    if browser not in browser_paths:
        return []
    
    browser_info = browser_paths[browser]
    profiles_dir = browser_info['profiles_dir']
    
    if not profiles_dir.exists():
        return []
    
    profiles = []
    
    if browser == 'firefox':
        # Firefox uses .default-release or .default profiles
        for path in profiles_dir.glob('*.default*'):
            if path.is_dir():
                profiles.append(path)
    else:
        # Chromium-based browsers use Default, Profile 1, Profile 2, etc.
        if (profiles_dir / 'Default').exists():
            profiles.append(profiles_dir / 'Default')
        
        # Look for additional profiles
        for path in profiles_dir.glob('Profile *'):
            if path.is_dir():
                profiles.append(path)
    
    return profiles


def get_cookie_db_path(browser: str, profile_path: Path) -> Optional[Path]:
    """Get the cookie database path for a browser profile
    
    Args:
        browser: Browser name
        profile_path: Path to the browser profile
        
    Returns:
        Path to cookie database file
    """
    browser_paths = get_browser_paths()
    
    if browser not in browser_paths:
        return None
    
    cookie_file = browser_paths[browser]['cookie_file']
    cookie_path = profile_path / cookie_file
    
    if cookie_path.exists():
        return cookie_path
    
    return None