#!/usr/bin/env python3
"""
Local cookie extractor that syncs cookies to remote VPS
"""
import json
import os
import time
import subprocess
from pathlib import Path
from typing import Dict, List
import browser_cookie3
import schedule

class LocalCookieExtractor:
    def __init__(self, vps_config: Dict):
        self.vps_host = vps_config["host"]
        self.vps_user = vps_config["user"]
        self.vps_path = vps_config["path"]
        self.local_cookie_dir = Path("cookies")
        self.local_cookie_dir.mkdir(exist_ok=True)
        
    def extract_cookies(self, platform: str) -> List[Dict]:
        """Extract cookies from local browser"""
        cookies = []
        
        # Map platforms to domains
        domain_map = {
            "youtube": ".youtube.com",
            "peertube": None,  # Multiple domains
            "odysee": ".odysee.com",
            "rumble": ".rumble.com"
        }
        
        domain = domain_map.get(platform)
        if not domain and platform != "peertube":
            print(f"Unknown platform: {platform}")
            return cookies
        
        try:
            # Try different browsers
            for browser in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.safari]:
                try:
                    browser_cookies = browser(domain_name=domain)
                    for cookie in browser_cookies:
                        if domain and domain in cookie.domain:
                            cookies.append({
                                "name": cookie.name,
                                "value": cookie.value,
                                "domain": cookie.domain,
                                "path": cookie.path,
                                "expires": cookie.expires,
                                "httpOnly": cookie.get_nonstandard_attr("HttpOnly", False),
                                "secure": cookie.secure
                            })
                    if cookies:
                        print(f"Found {len(cookies)} cookies from {browser.__name__}")
                        break
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error extracting cookies for {platform}: {e}")
            
        return cookies
    
    def save_cookies_locally(self, platform: str, cookies: List[Dict]):
        """Save cookies to local file"""
        cookie_file = self.local_cookie_dir / f"{platform}_cookies.json"
        with open(cookie_file, "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved {len(cookies)} cookies for {platform} locally")
    
    def sync_to_vps(self, platform: str):
        """Sync cookies to VPS using rsync or scp"""
        local_file = self.local_cookie_dir / f"{platform}_cookies.json"
        if not local_file.exists():
            print(f"No cookies found for {platform}")
            return
            
        remote_path = f"{self.vps_user}@{self.vps_host}:{self.vps_path}/data/cookies/"
        
        try:
            # Use rsync for efficient transfer
            cmd = [
                "rsync", "-avz", "--mkpath",
                str(local_file),
                remote_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"Successfully synced {platform} cookies to VPS")
            else:
                print(f"Failed to sync: {result.stderr}")
                # Fallback to scp
                cmd = ["scp", str(local_file), remote_path]
                subprocess.run(cmd)
                
        except Exception as e:
            print(f"Error syncing to VPS: {e}")
    
    def extract_and_sync(self, platform: str):
        """Extract cookies and sync to VPS"""
        print(f"\nProcessing {platform}...")
        cookies = self.extract_cookies(platform)
        if cookies:
            self.save_cookies_locally(platform, cookies)
            self.sync_to_vps(platform)
        else:
            print(f"No cookies found for {platform}")
    
    def run_once(self):
        """Run extraction once for all platforms"""
        platforms = ["youtube", "odysee", "rumble"]
        for platform in platforms:
            self.extract_and_sync(platform)
    
    def run_scheduled(self, interval_hours: int = 24):
        """Run extraction on schedule"""
        print(f"Starting scheduled extraction every {interval_hours} hours")
        
        # Run once immediately
        self.run_once()
        
        # Schedule periodic runs
        schedule.every(interval_hours).hours.do(self.run_once)
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # Configuration for your VPS
    vps_config = {
        "host": "your-vps-ip",  # Replace with your VPS IP
        "user": "your-username",  # Replace with your VPS username
        "path": "/home/your-username/robustty"  # Replace with bot path on VPS
    }
    
    extractor = LocalCookieExtractor(vps_config)
    
    # Run once
    extractor.run_once()
    
    # Or run on schedule (uncomment to use)
    # extractor.run_scheduled(interval_hours=24)