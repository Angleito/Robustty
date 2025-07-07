#!/bin/bash

echo "Fixing Redis memory overcommit warning..."
echo ""
echo "This script will set vm.overcommit_memory=1 to fix Redis warning."
echo "This setting allows Redis to perform background saves without failing due to memory constraints."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "This script needs to be run with sudo to modify sysctl settings."
    echo "Usage: sudo $0"
    exit 1
fi

# Set the value temporarily
echo "Setting vm.overcommit_memory=1 temporarily..."
sysctl vm.overcommit_memory=1

# Make it persistent
echo "Making the change persistent..."
if ! grep -q "vm.overcommit_memory" /etc/sysctl.conf; then
    echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf
    echo "Added vm.overcommit_memory=1 to /etc/sysctl.conf"
else
    # Update existing value
    sed -i 's/^vm.overcommit_memory.*/vm.overcommit_memory = 1/' /etc/sysctl.conf
    echo "Updated vm.overcommit_memory in /etc/sysctl.conf"
fi

# Reload sysctl
sysctl -p

echo ""
echo "✅ Redis memory overcommit warning has been fixed!"
echo "The setting will persist across reboots."
echo ""
echo "You can verify the setting with: sysctl vm.overcommit_memory"