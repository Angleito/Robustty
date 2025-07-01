#!/bin/bash

# Convert JSON cookies to Netscape format on VPS
# Run this on the VPS after copying cookies

set -e

echo "=== Cookie Conversion Script ==="
echo
echo "Converting JSON cookies to Netscape format for yt-dlp"
echo

# Find Robustty directory
ROBUSTTY_DIR=$(find /root /home -name "Robustty" -type d 2>/dev/null | head -1)
if [ -z "$ROBUSTTY_DIR" ]; then
    echo "Cannot find Robustty directory"
    exit 1
fi

cd "$ROBUSTTY_DIR"

# Create Python script for conversion
cat > convert_cookies_temp.py << 'EOF'
#!/usr/bin/env python3
import json
import os
from pathlib import Path

def json_to_netscape(json_file, txt_file):
    """Convert JSON cookies to Netscape format"""
    try:
        with open(json_file, 'r') as f:
            cookies = json.load(f)
        
        # Handle different JSON formats
        if isinstance(cookies, dict) and 'cookies' in cookies:
            cookies = cookies['cookies']
        elif not isinstance(cookies, list):
            print(f"Unexpected format in {json_file}")
            return False
        
        with open(txt_file, 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This is a generated file! Do not edit.\n\n")
            
            for cookie in cookies:
                # Extract cookie fields
                domain = cookie.get('domain', '')
                if domain.startswith('.'):
                    include_subdomains = 'TRUE'
                else:
                    include_subdomains = 'FALSE'
                    domain = '.' + domain
                
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expires = str(int(cookie.get('expirationDate', 0)))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                # Write in Netscape format
                f.write(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        
        print(f"✓ Converted {json_file} to {txt_file}")
        return True
    except Exception as e:
        print(f"✗ Failed to convert {json_file}: {e}")
        return False

# Convert all platform cookies
cookie_dir = Path("cookies")
platforms = ['youtube', 'rumble', 'odysee', 'peertube']

for platform in platforms:
    json_file = cookie_dir / f"{platform}_cookies.json"
    txt_file = cookie_dir / f"{platform}_cookies.txt"
    
    if json_file.exists():
        json_to_netscape(json_file, txt_file)
    else:
        print(f"No {platform} cookies found")

print("\nCookie conversion complete!")
EOF

# Run the conversion
echo "Converting cookies..."
python3 convert_cookies_temp.py

# Clean up
rm -f convert_cookies_temp.py

# Update permissions
chown -R 1000:1000 cookies/
chmod 644 cookies/*.txt 2>/dev/null || true

# Show results
echo
echo "Converted cookie files:"
ls -la cookies/*.txt 2>/dev/null || echo "No .txt files created"

# Restart bot to use new cookies
echo
echo "Restarting bot..."
docker-compose restart robustty

echo
echo "=== Conversion Complete ==="
echo
echo "Cookies have been converted to Netscape format!"
echo "Monitor logs with: docker-compose logs -f robustty"