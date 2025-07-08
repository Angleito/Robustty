#!/bin/bash

# Toggle ProtonVPN for bot operations
# This script can disable VPN, run bot, then re-enable

echo "🔄 ProtonVPN Toggle Script"
echo "========================="

case "$1" in
  "off")
    echo "🛑 Disconnecting from ProtonVPN..."
    protonvpn-cli disconnect
    sleep 3
    echo "✅ VPN disconnected"
    echo "🔄 Restarting bot without VPN..."
    cd /root/Robustty
    docker-compose restart robustty
    ;;
    
  "on")
    echo "🟢 Connecting to ProtonVPN..."
    protonvpn-cli connect -f
    sleep 5
    protonvpn-cli status
    echo "✅ VPN connected"
    ;;
    
  "test")
    echo "🧪 Testing with VPN disabled temporarily..."
    # Disconnect VPN
    protonvpn-cli disconnect
    sleep 3
    
    # Test bot
    cd /root/Robustty
    docker-compose restart robustty
    sleep 10
    
    echo "📊 Testing music search..."
    docker-compose exec robustty python3 -c "
import asyncio
from src.platforms.youtube import YouTube

async def test():
    yt = YouTube()
    results = await yt.search_videos('test', 1)
    print(f'Search test: {results}')

asyncio.run(test())
"
    
    # Reconnect VPN
    echo "🔄 Reconnecting VPN..."
    protonvpn-cli connect -f
    ;;
    
  *)
    echo "Usage: $0 {off|on|test}"
    echo "  off  - Disconnect VPN and restart bot"
    echo "  on   - Reconnect to VPN"
    echo "  test - Test bot without VPN temporarily"
    exit 1
    ;;
esac