"""Platform-specific cookie decryption functionality"""
import base64
import json
import logging
import subprocess
from typing import Optional
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


def decrypt_value(encrypted_value: bytes, browser: str) -> Optional[str]:
    """Decrypt cookie value based on platform and browser
    
    Args:
        encrypted_value: Encrypted cookie value
        browser: Browser name
        
    Returns:
        Decrypted value or None if decryption fails
    """
    if not encrypted_value:
        return None
    
    try:
        from .browser_paths import detect_os
        os_name = detect_os()
        
        if os_name == 'windows':
            return decrypt_windows(encrypted_value)
        elif os_name == 'macos':
            return decrypt_macos(encrypted_value, browser)
        elif os_name == 'linux':
            return decrypt_linux(encrypted_value)
        else:
            logger.error(f"Unsupported OS for decryption: {os_name}")
            return None
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return None


def decrypt_windows(encrypted_value: bytes) -> Optional[str]:
    """Decrypt cookies on Windows using DPAPI
    
    Args:
        encrypted_value: Encrypted cookie value
        
    Returns:
        Decrypted value
    """
    try:
        import win32crypt
        
        # Windows DPAPI decryption
        decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)
        return decrypted[1].decode('utf-8')
    except ImportError:
        logger.warning("win32crypt not available, trying alternative method")
        
        # Alternative method using ctypes
        try:
            import ctypes
            import ctypes.wintypes
            
            DATA_BLOB = ctypes.c_void_p
            
            class CRYPTPROTECT_FLAGS:
                CRYPTPROTECT_UI_FORBIDDEN = 0x01
                CRYPTPROTECT_LOCAL_MACHINE = 0x04
            
            def decrypt_dpapi(encrypted_data: bytes) -> bytes:
                buffer_in = ctypes.create_string_buffer(encrypted_data, len(encrypted_data))
                buffer_out = DATA_BLOB()
                
                if ctypes.windll.crypt32.CryptUnprotectData(
                    ctypes.pointer(buffer_in),
                    None,
                    None,
                    None,
                    None,
                    CRYPTPROTECT_FLAGS.CRYPTPROTECT_UI_FORBIDDEN,
                    ctypes.pointer(buffer_out)
                ):
                    return ctypes.string_at(buffer_out.value)
                else:
                    raise Exception("Failed to decrypt")
            
            return decrypt_dpapi(encrypted_value).decode('utf-8')
        except Exception as e:
            logger.error(f"Windows decryption failed: {e}")
            return None


def decrypt_macos(encrypted_value: bytes, browser: str) -> Optional[str]:
    """Decrypt cookies on macOS using Keychain
    
    Args:
        encrypted_value: Encrypted cookie value
        browser: Browser name
        
    Returns:
        Decrypted value
    """
    if len(encrypted_value) <= 3:
        return None
    
    # Check if value is encrypted (starts with 'v10' or 'v11')
    if encrypted_value[:3] != b'v10' and encrypted_value[:3] != b'v11':
        return encrypted_value.decode('utf-8', errors='ignore')
    
    # Extract encrypted data
    encrypted_data = encrypted_value[3:]
    
    # Get keychain key
    key = get_keychain_key(browser)
    if not key:
        logger.error(f"Failed to get keychain key for {browser}")
        return None
    
    # Decrypt using AES
    try:
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(b' ' * 16),  # Chrome uses spaces as IV
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Remove padding
        padding_length = decrypted[-1]
        return decrypted[:-padding_length].decode('utf-8')
    except Exception as e:
        logger.error(f"macOS decryption error: {e}")
        return None


def decrypt_linux(encrypted_value: bytes) -> Optional[str]:
    """Decrypt cookies on Linux
    
    Linux Chrome uses a simpler encryption scheme or plain text
    
    Args:
        encrypted_value: Encrypted cookie value
        
    Returns:
        Decrypted value
    """
    if len(encrypted_value) <= 3:
        return None
    
    # Check if value is encrypted (starts with 'v10' or 'v11')
    if encrypted_value[:3] == b'v10' or encrypted_value[:3] == b'v11':
        # Linux uses a fixed key 'peanuts' for v10 encryption
        key = b'peanuts'
        encrypted_data = encrypted_value[3:]
        
        try:
            cipher = Cipher(
                algorithms.AES(key.ljust(16, b' ')),  # Pad key to 16 bytes
                modes.CBC(b' ' * 16),  # Use spaces as IV
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Remove padding
            padding_length = decrypted[-1]
            return decrypted[:-padding_length].decode('utf-8')
        except Exception as e:
            logger.error(f"Linux decryption error: {e}")
            return None
    else:
        # Not encrypted, return as is
        return encrypted_value.decode('utf-8', errors='ignore')


def get_keychain_key(browser: str) -> Optional[bytes]:
    """Get encryption key from macOS Keychain
    
    Args:
        browser: Browser name
        
    Returns:
        Encryption key bytes
    """
    service_name = _get_keychain_service(browser)
    
    try:
        # Use security command to get keychain entry
        cmd = [
            'security', 'find-generic-password',
            '-s', service_name,
            '-w'  # Output only the password
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            password = result.stdout.strip()
            key = base64.b64decode(password)
            return key
        else:
            logger.error(f"Failed to get keychain key: {result.stderr}")
            
            # Try alternative method using Python keyring
            try:
                import keyring
                password = keyring.get_password(service_name, "Chrome")
                if password:
                    return base64.b64decode(password)
            except ImportError:
                logger.warning("keyring module not available")
            
            return None
    except Exception as e:
        logger.error(f"Keychain access error: {e}")
        return None


def _get_keychain_service(browser: str) -> str:
    """Get the keychain service name for a browser
    
    Args:
        browser: Browser name
        
    Returns:
        Keychain service name
    """
    service_map = {
        'chrome': 'Chrome Safe Storage',
        'chromium': 'Chromium Safe Storage',
        'edge': 'Microsoft Edge Safe Storage',
        'brave': 'Brave Safe Storage',
        'opera': 'Opera Safe Storage'
    }
    
    return service_map.get(browser.lower(), 'Chrome Safe Storage')