# Cross-Platform Cookie Extraction

This document describes the cross-platform cookie extraction system for Robustty.

## Overview

The cookie extraction system automatically detects and extracts cookies from installed browsers on Windows and macOS. It supports all major browsers and provides a unified API for cookie management.

## Supported Platforms

- Windows (10/11)
- macOS (10.15+)
- Linux (experimental)

## Supported Browsers

- Google Chrome
- Chromium
- Microsoft Edge
- Brave
- Opera
- Mozilla Firefox

## Architecture

The system consists of several modules:

1. **`browser_paths.py`**: OS detection and browser profile discovery
2. **`cookie_database.py`**: SQLite database reading and cookie extraction
3. **`cookie_decryption.py`**: Platform-specific cookie decryption
4. **`cross_platform_cookies.py`**: Unified API for cookie extraction

## Usage

### Basic Usage

```python
from src.extractors.cross_platform_cookies import CrossPlatformCookieExtractor

# Create extractor
extractor = CrossPlatformCookieExtractor()

# Extract all cookies
all_cookies = extractor.extract_all_cookies()

# Get YouTube cookies specifically
youtube_cookies = extractor.find_youtube_cookies()

# Get platform-specific cookies
rumble_cookies = extractor.find_platform_cookies('rumble')
```

### Integration with Cookie Manager

The `CookieManager` class has been updated to use the cross-platform extractor:

```python
from src.services.cookie_manager import CookieManager

# Create manager
manager = CookieManager(config)

# Extract cookies for a platform
await manager.extract_browser_cookies('youtube')

# Get cookies
cookies = manager.get_cookies('youtube')
```

## How It Works

### 1. OS Detection

The system first detects the operating system using `platform.system()`:
- Windows → 'windows'
- Darwin (macOS) → 'macos'
- Linux → 'linux'

### 2. Browser Profile Discovery

For each browser, the system locates profile directories:

**Windows:**
- Chrome: `%LOCALAPPDATA%\Google\Chrome\User Data`
- Firefox: `%APPDATA%\Mozilla\Firefox\Profiles`

**macOS:**
- Chrome: `~/Library/Application Support/Google/Chrome`
- Firefox: `~/Library/Application Support/Firefox/Profiles`

### 3. Cookie Extraction

The system reads cookies from SQLite databases:
- Chromium-based browsers: `Cookies` file
- Firefox: `cookies.sqlite` file

### 4. Cookie Decryption

Platform-specific decryption is applied:

**Windows:**
- Uses Windows DPAPI (`CryptUnprotectData`)
- Falls back to ctypes if win32crypt unavailable

**macOS:**
- Reads encryption key from Keychain
- Decrypts using AES-128-CBC

**Linux:**
- Uses fixed key 'peanuts' for v10 encryption
- Plain text for unencrypted cookies

### 5. Cookie Filtering

The system filters cookies by:
- Expiration date (removes expired cookies)
- Domain (only includes relevant domains)

## Security Considerations

1. **Temporary Files**: Cookie databases are copied to temp files to avoid lock conflicts
2. **Encryption Keys**: Platform-specific keys are handled securely
3. **No Credential Storage**: The system doesn't store browser credentials

## Troubleshooting

### Common Issues

1. **No cookies found**
   - Ensure browser is installed and has been used
   - Check browser profile exists
   - Verify user has logged into the target site

2. **Decryption failures**
   - On Windows: Ensure running with same user account
   - On macOS: Grant Keychain access when prompted
   - Check system logs for detailed errors

3. **Permission errors**
   - Run with appropriate permissions
   - On macOS: May need to grant Full Disk Access

### Debug Logging

Enable debug logging to troubleshoot:

```python
import logging
logging.getLogger('src.extractors').setLevel(logging.DEBUG)
```

## Migration from browser_cookie3

The new system replaces the optional `browser_cookie3` dependency:

1. No external dependencies required (except cryptography)
2. Better error handling and logging
3. Supports more browsers
4. More reliable on macOS and Windows

To migrate:
1. Update imports to use `CrossPlatformCookieExtractor`
2. Replace `browser_cookie3` calls with new API
3. Update error handling

## Testing

Run the test suite:

```bash
pytest tests/test_extractors/
```

Integration tests:
```bash
pytest tests/test_extractors/test_integration_cookies.py
```

## Examples

### Extract cookies for multiple platforms

```python
async def extract_all_platform_cookies():
    manager = CookieManager(config)
    
    platforms = ['youtube', 'rumble', 'odysee']
    for platform in platforms:
        await manager.extract_browser_cookies(platform)
        cookies = manager.get_cookies(platform)
        print(f"{platform}: {len(cookies)} cookies")
```

### Use cookies with requests

```python
import requests

extractor = CrossPlatformCookieExtractor()
cookie_jar = extractor.find_youtube_cookies()

response = requests.get('https://youtube.com/feed', cookies=cookie_jar)
```

### Save cookies for yt-dlp

```python
extractor = CrossPlatformCookieExtractor()
extractor.save_cookies_json(
    Path('cookies/youtube_cookies.json'),
    domains=['youtube.com', '.youtube.com']
)
```

## Future Improvements

1. Add support for Safari on macOS
2. Improve Linux support for more distributions
3. Add cookie injection capabilities
4. Support for mobile browser sync
5. Encrypted cookie storage

## References

- [Chromium Cookie Encryption](https://www.chromium.org/developers/design-documents/os-x-password-manager-keychain-integration/)
- [Firefox Cookie Storage](https://developer.mozilla.org/en-US/docs/Mozilla/Tech/Places/Database)
- [Windows DPAPI](https://docs.microsoft.com/en-us/windows/win32/api/dpapi/)