#!/usr/bin/env python3
"""
Automatic Cookie Sync to VPS
Runs after each cookie extraction to sync cookies to VPS
"""
import os
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_cookies_to_vps():
    """Sync cookies to VPS using unified SSH approach with minimal connections"""
    
    # Get VPS configuration from environment
    vps_host = os.getenv('VPS_HOST')
    vps_user = os.getenv('VPS_USER', 'ubuntu')
    vps_path = os.getenv('VPS_PATH', '~/robustty-bot/cookies')
    ssh_key = os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa')
    
    if not vps_host:
        logger.warning("VPS_HOST not set, skipping cookie sync")
        return False
    
    cookie_dir = Path('/app/cookies')
    if not cookie_dir.exists():
        logger.error("Cookie directory not found")
        return False
    
    # Create timestamp file
    timestamp_file = cookie_dir / 'last_sync.txt'
    timestamp_file.write_text(datetime.now().isoformat())
    
    # Count cookies to sync
    cookie_files = list(cookie_dir.glob('*.json'))
    if not cookie_files:
        logger.warning("No cookie files found to sync")
        return False
    
    logger.info(f"Preparing to sync {len(cookie_files)} cookie files to VPS")
    
    try:
        # Use unified sync script if available, otherwise fall back to rsync
        unified_script = Path(__file__).parent / 'unified-vps-sync.sh'
        
        if unified_script.exists():
            logger.info("Using unified VPS sync script for optimized performance")
            
            # Set environment variables for the script
            env = os.environ.copy()
            env.update({
                'VPS_HOST': vps_host,
                'VPS_USER': vps_user,
                'VPS_PATH': vps_path,
                'SSH_KEY_PATH': ssh_key
            })
            
            cmd = ['bash', str(unified_script)]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                logger.info("✅ Unified cookie sync completed successfully")
                logger.debug(f"Sync output: {result.stdout[-500:]}")
                return True
            else:
                logger.error(f"❌ Unified cookie sync failed: {result.stderr}")
                # Fall back to traditional rsync
                logger.info("Falling back to traditional rsync method")
        
        # Traditional rsync approach (fallback or when unified script not available)
        logger.info(f"Syncing cookies to {vps_user}@{vps_host}:{vps_path} using rsync")
        
        # Use SSH multiplexing options for efficiency
        ssh_options = [
            '-o', 'ControlMaster=auto',
            '-o', 'ControlPath=/tmp/ssh_%h_%p_%r',
            '-o', 'ControlPersist=600',
            '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=60'
        ]
        
        if os.path.exists(os.path.expanduser(ssh_key)):
            ssh_options.extend(['-i', os.path.expanduser(ssh_key)])
        
        ssh_command = 'ssh ' + ' '.join(ssh_options)
        
        # First, prepare remote environment in single SSH call
        prep_commands = [
            f'mkdir -p {vps_path}',
            f'[ -d "{vps_path}" ] && find {vps_path} -name "*.json" -type f -delete || true',
            f'echo "Remote environment prepared at $(date)"'
        ]
        
        prep_script = ' && '.join(prep_commands)
        ssh_prep_cmd = f'{ssh_command} {vps_user}@{vps_host} "{prep_script}"'
        
        logger.info("Preparing remote environment")
        result = subprocess.run(ssh_prep_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.warning(f"Remote preparation warning: {result.stderr}")
        
        # Sync cookies using rsync with SSH multiplexing
        rsync_cmd = [
            'rsync', '-avz', '--delete', '--progress',
            '-e', ssh_command,
            f'{cookie_dir}/',
            f'{vps_user}@{vps_host}:{vps_path}/'
        ]
        
        result = subprocess.run(rsync_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Cookie sync completed successfully")
            
            # Verify sync in single SSH call
            verify_cmd = f'{ssh_command} {vps_user}@{vps_host} "find {vps_path} -name \'*.json\' | wc -l"'
            verify_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True)
            
            if verify_result.returncode == 0:
                remote_count = verify_result.stdout.strip()
                logger.info(f"📊 Verification: {remote_count} cookie files on remote VPS")
            
            return True
        else:
            logger.error(f"❌ Cookie sync failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error syncing cookies: {e}")
        return False

def main():
    """Main function called after cookie extraction"""
    logger.info("Starting automatic cookie sync to VPS")
    
    # Check if auto-sync is enabled
    if os.getenv('AUTO_SYNC_VPS', 'false').lower() != 'true':
        logger.info("Auto-sync to VPS is disabled (set AUTO_SYNC_VPS=true to enable)")
        return
    
    # Perform sync
    success = sync_cookies_to_vps()
    
    if success:
        logger.info("✅ Cookies successfully synced to VPS")
    else:
        logger.warning("⚠️  Cookie sync to VPS failed or skipped")

if __name__ == '__main__':
    main()