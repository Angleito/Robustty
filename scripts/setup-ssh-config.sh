#!/bin/bash
# Setup SSH configuration for cookie sync

# Create SSH directory
mkdir -p /root/.ssh

# Set proper permissions on SSH key
if [ -f /root/.ssh/id_rsa ]; then
    chmod 600 /root/.ssh/id_rsa
fi

# Create SSH config to disable host key checking for automated sync
cat > /root/.ssh/config << EOF
Host *
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
EOF

chmod 644 /root/.ssh/config