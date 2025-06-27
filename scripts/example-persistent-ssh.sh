#!/bin/bash

# Example: Using Persistent SSH for Robustty Deployment Tasks
# This script demonstrates how to use the SSH persistent connection manager
# for various deployment and maintenance tasks

set -e

# Source the SSH persistent connection manager
SCRIPT_DIR="$(dirname "$0")"
source "$SCRIPT_DIR/ssh-persistent.sh"

# Configuration
VPS_HOST="${VPS_HOST:-your-vps-ip}"
VPS_USER="${VPS_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-~/.ssh/id_rsa}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Example usage functions

# 1. Deploy and monitor using persistent SSH
deploy_with_persistent_ssh() {
    echo -e "${BLUE}🚀 Deploying Robustty with Persistent SSH${NC}"
    
    # Establish the connection once
    log INFO "Establishing persistent SSH connection..."
    ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"
    
    # Perform multiple operations using the same connection
    log INFO "Creating deployment directory..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "mkdir -p ~/robustty-deployment"
    
    log INFO "Copying configuration files..."
    ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "./docker-compose.yml" "~/robustty-deployment/"
    ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "./.env" "~/robustty-deployment/"
    
    log INFO "Installing dependencies..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "cd ~/robustty-deployment && docker-compose pull"
    
    log INFO "Starting services..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "cd ~/robustty-deployment && docker-compose up -d"
    
    log INFO "Checking service status..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "cd ~/robustty-deployment && docker-compose ps"
    
    echo -e "${GREEN}✅ Deployment completed using persistent SSH connection${NC}"
}

# 2. Sync cookies with persistent connection
sync_cookies_persistent() {
    echo -e "${BLUE}🍪 Syncing cookies with persistent SSH${NC}"
    
    # Establish connection if not already connected
    if ! ssh_is_connected "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"; then
        ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"
    fi
    
    # Create remote cookie directory
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "mkdir -p ~/robustty-deployment/cookies"
    
    # Sync cookies (assuming local cookies directory exists)
    if [[ -d "./cookies" ]]; then
        log INFO "Syncing cookies to VPS..."
        ssh_copy_persistent "to" "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "./cookies/" "~/robustty-deployment/cookies/"
        
        # Restart bot to pick up new cookies
        ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "cd ~/robustty-deployment && docker-compose restart"
        
        echo -e "${GREEN}✅ Cookies synced and bot restarted${NC}"
    else
        log WARN "No local cookies directory found"
    fi
}

# 3. Monitor logs and health with persistent connection
monitor_deployment() {
    echo -e "${BLUE}📊 Monitoring deployment with persistent SSH${NC}"
    
    # Ensure connection is established
    ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"
    
    # Check system resources
    log INFO "Checking system resources..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "free -h && df -h /"
    
    # Check Docker status
    log INFO "Checking Docker containers..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "cd ~/robustty-deployment && docker-compose ps"
    
    # Check recent logs
    log INFO "Recent logs:"
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "cd ~/robustty-deployment && docker-compose logs --tail=20"
    
    # Test bot connectivity
    log INFO "Testing bot connectivity..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "curl -f http://localhost:8080/health || echo 'Health check failed'"
    
    echo -e "${GREEN}✅ Monitoring completed${NC}"
}

# 4. Backup with persistent connection
backup_deployment() {
    echo -e "${BLUE}💾 Creating backup with persistent SSH${NC}"
    
    ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"
    
    # Create backup directory with timestamp
    local backup_name="robustty-backup-$(date +%Y%m%d-%H%M%S)"
    
    log INFO "Creating backup: $backup_name"
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "
        mkdir -p ~/backups
        cd ~
        tar -czf ~/backups/$backup_name.tar.gz robustty-deployment/
        ls -la ~/backups/$backup_name.tar.gz
    "
    
    # Optionally download backup
    read -p "Download backup to local machine? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log INFO "Downloading backup..."
        ssh_copy_persistent "from" "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "~/backups/$backup_name.tar.gz" "./"
        echo -e "${GREEN}✅ Backup downloaded to ./$backup_name.tar.gz${NC}"
    fi
    
    echo -e "${GREEN}✅ Backup created${NC}"
}

# 5. Cleanup and maintenance with persistent connection
maintenance_tasks() {
    echo -e "${BLUE}🧹 Running maintenance with persistent SSH${NC}"
    
    ssh_connect_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"
    
    # Clean up Docker
    log INFO "Cleaning up Docker images..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "docker system prune -f"
    
    # Update packages (if desired)
    log INFO "Checking for package updates..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "sudo apt update && sudo apt list --upgradable"
    
    # Clean up old backups (keep last 5)
    log INFO "Cleaning up old backups..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "
        cd ~/backups 2>/dev/null || exit 0
        ls -t *.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
        echo \"Remaining backups: \$(ls *.tar.gz 2>/dev/null | wc -l)\"
    "
    
    # Rotate logs
    log INFO "Rotating logs..."
    ssh_exec_persistent "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY" "
        cd ~/robustty-deployment
        docker-compose exec -T robustty find /app/logs -name '*.log' -mtime +7 -delete 2>/dev/null || true
    "
    
    echo -e "${GREEN}✅ Maintenance completed${NC}"
}

# Menu system
show_menu() {
    echo -e "${BLUE}🔧 Robustty Persistent SSH Management${NC}"
    echo "=================================="
    echo "1. Deploy with persistent SSH"
    echo "2. Sync cookies"
    echo "3. Monitor deployment"
    echo "4. Create backup"
    echo "5. Run maintenance"
    echo "6. List active SSH connections"
    echo "7. Test SSH connection"
    echo "8. Disconnect SSH"
    echo "9. Exit"
    echo ""
}

# Main execution
main() {
    # Check configuration
    if [[ "$VPS_HOST" == "your-vps-ip" ]]; then
        echo -e "${RED}❌ Please configure VPS_HOST${NC}"
        echo "Set environment variable: export VPS_HOST=your.vps.ip"
        exit 1
    fi
    
    if [[ $# -eq 0 ]]; then
        # Interactive mode
        while true; do
            show_menu
            read -p "Select option (1-9): " choice
            echo ""
            
            case $choice in
                1) deploy_with_persistent_ssh ;;
                2) sync_cookies_persistent ;;
                3) monitor_deployment ;;
                4) backup_deployment ;;
                5) maintenance_tasks ;;
                6) ssh_list_persistent ;;
                7) 
                    if ssh_is_connected "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"; then
                        echo -e "${GREEN}✅ SSH connection is active${NC}"
                    else
                        echo -e "${YELLOW}❌ No active SSH connection${NC}"
                    fi
                    ;;
                8) ssh_disconnect_persistent "$VPS_HOST" "$VPS_USER" "22" ;;
                9) 
                    echo "Goodbye!"
                    # Clean up connections on exit
                    ssh_disconnect_persistent "$VPS_HOST" "$VPS_USER" "22"
                    exit 0
                    ;;
                *) echo -e "${RED}Invalid option${NC}" ;;
            esac
            echo ""
            read -p "Press Enter to continue..."
            echo ""
        done
    else
        # Command line mode
        case "$1" in
            deploy) deploy_with_persistent_ssh ;;
            sync) sync_cookies_persistent ;;
            monitor) monitor_deployment ;;
            backup) backup_deployment ;;
            maintenance) maintenance_tasks ;;
            list) ssh_list_persistent ;;
            test) 
                if ssh_is_connected "$VPS_HOST" "$VPS_USER" "22" "$SSH_KEY"; then
                    echo "SSH connection is active"
                    exit 0
                else
                    echo "No active SSH connection"
                    exit 1
                fi
                ;;
            disconnect) ssh_disconnect_persistent "$VPS_HOST" "$VPS_USER" "22" ;;
            *)
                echo "Usage: $0 [deploy|sync|monitor|backup|maintenance|list|test|disconnect]"
                echo "Run without arguments for interactive mode"
                exit 1
                ;;
        esac
    fi
}

# Check if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
