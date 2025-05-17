"""SQLite cookie database extraction functionality"""
import sqlite3
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class Cookie:
    """Represents a browser cookie"""
    host_key: str
    name: str
    value: str
    path: str
    expires_utc: Optional[int]
    is_secure: bool
    is_httponly: bool
    encrypted_value: Optional[bytes] = None
    samesite: str = "None"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'name': self.name,
            'value': self.value,
            'domain': self.host_key,
            'path': self.path,
            'secure': self.is_secure,
            'httpOnly': self.is_httponly,
            'sameSite': self.samesite,
            'expires': self.expires_utc
        }


def extract_sqlite_cookies(db_path: Path) -> List[Cookie]:
    """Extract cookies from SQLite database file
    
    Args:
        db_path: Path to the cookies SQLite file
        
    Returns:
        List of Cookie objects
    """
    cookies = []
    
    # Copy database to temp location to avoid lock conflicts
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        try:
            shutil.copy2(db_path, tmp_file.name)
            
            # Connect to the copied database
            conn = sqlite3.connect(tmp_file.name)
            cursor = conn.cursor()
            
            # Query based on browser type
            if 'firefox' in str(db_path).lower() or 'mozilla' in str(db_path).lower():
                # Firefox schema
                query = """
                SELECT host, name, value, path, expiry, isSecure, isHttpOnly
                FROM moz_cookies
                """
                cursor.execute(query)
                
                for row in cursor.fetchall():
                    host, name, value, path, expiry, is_secure, is_httponly = row
                    cookies.append(Cookie(
                        host_key=host,
                        name=name,
                        value=value,
                        path=path,
                        expires_utc=expiry,
                        is_secure=bool(is_secure),
                        is_httponly=bool(is_httponly)
                    ))
            else:
                # Chromium-based schema
                query = """
                SELECT host_key, name, value, encrypted_value, path, 
                       expires_utc, is_secure, is_httponly
                FROM cookies
                """
                cursor.execute(query)
                
                for row in cursor.fetchall():
                    host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly = row
                    
                    # Convert Chrome timestamps (microseconds since Jan 1, 1601)
                    # to Unix timestamps
                    if expires_utc:
                        expires_utc = chrome_timestamp_to_unix(expires_utc)
                    
                    cookies.append(Cookie(
                        host_key=host_key,
                        name=name,
                        value=value,
                        path=path,
                        expires_utc=expires_utc,
                        is_secure=bool(is_secure),
                        is_httponly=bool(is_httponly),
                        encrypted_value=encrypted_value
                    ))
            
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"SQLite error reading {db_path}: {e}")
        except Exception as e:
            logger.error(f"Error extracting cookies from {db_path}: {e}")
        finally:
            # Clean up temp file
            Path(tmp_file.name).unlink(missing_ok=True)
    
    return cookies


def chrome_timestamp_to_unix(chrome_timestamp: int) -> int:
    """Convert Chrome timestamp to Unix timestamp
    
    Chrome timestamps are microseconds since Jan 1, 1601
    Unix timestamps are seconds since Jan 1, 1970
    """
    # Number of seconds between Jan 1, 1601 and Jan 1, 1970
    epoch_diff = 11644473600
    
    # Convert microseconds to seconds and adjust for epoch difference
    return (chrome_timestamp // 1000000) - epoch_diff


def filter_expired_cookies(cookies: List[Cookie]) -> List[Cookie]:
    """Filter out expired cookies
    
    Args:
        cookies: List of cookies to filter
        
    Returns:
        List of non-expired cookies
    """
    current_time = int(datetime.now(timezone.utc).timestamp())
    
    filtered = []
    for cookie in cookies:
        if cookie.expires_utc is None or cookie.expires_utc > current_time:
            filtered.append(cookie)
        else:
            logger.debug(f"Filtering expired cookie: {cookie.name}")
    
    return filtered


def filter_cookies_by_domain(cookies: List[Cookie], domains: List[str]) -> List[Cookie]:
    """Filter cookies by domain
    
    Args:
        cookies: List of cookies to filter
        domains: List of domain patterns to match
        
    Returns:
        List of cookies matching the domains
    """
    filtered = []
    
    for cookie in cookies:
        for domain in domains:
            if domain.startswith('.'):
                # Match any subdomain
                if cookie.host_key.endswith(domain) or cookie.host_key == domain[1:]:
                    filtered.append(cookie)
                    break
            else:
                # Exact match
                if cookie.host_key == domain or cookie.host_key == f".{domain}":
                    filtered.append(cookie)
                    break
    
    return filtered