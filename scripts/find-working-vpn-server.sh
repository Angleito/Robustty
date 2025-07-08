#!/bin/bash

# Find ProtonVPN servers that work with YouTube
echo "🔍 Finding VPN Servers that Work with YouTube"
echo "==========================================="

# Test servers
SERVERS=("US-FREE#1" "US-FREE#2" "NL-FREE#1" "JP-FREE#1" "CH-FREE#1")

for server in "${SERVERS[@]}"; do
    echo "Testing $server..."
    
    # Connect to server
    protonvpn-cli connect $server
    sleep 5
    
    # Test YouTube
    if curl -s "https://www.youtube.com" > /dev/null; then
        echo "✅ $server - YouTube accessible"
        
        # Test search
        docker-compose exec robustty yt-dlp --dump-json "ytsearch:test" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "✅ $server - YouTube search works!"
            echo "🎉 Found working server: $server"
            break
        else
            echo "❌ $server - YouTube search blocked"
        fi
    else
        echo "❌ $server - YouTube blocked"
    fi
done

echo ""
echo "If a working server was found, use:"
echo "protonvpn-cli connect <server-name>"