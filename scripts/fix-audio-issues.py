#!/usr/bin/env python3
"""
Audio Pipeline Issue Fixer for Robustty

This script provides automated fixes for common audio pipeline issues
identified by the diagnostic tool.

Usage:
    python scripts/fix-audio-issues.py --check
    python scripts/fix-audio-issues.py --fix-all
    python scripts/fix-audio-issues.py --fix-cookies
    python scripts/fix-audio-issues.py --fix-ffmpeg
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioIssueFixer:
    """Automated fixer for common audio pipeline issues"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.fixes_applied = []
        self.issues_found = []
    
    def check_all_issues(self) -> Dict[str, bool]:
        """Check for all common audio pipeline issues"""
        logger.info("Checking for audio pipeline issues...")
        
        issues = {
            "ffmpeg_missing": not self._check_ffmpeg(),
            "cookies_missing": not self._check_cookies(),
            "environment_incomplete": not self._check_environment(),
            "dependencies_missing": not self._check_dependencies(),
            "permissions_incorrect": not self._check_permissions(),
        }
        
        found_issues = [k for k, v in issues.items() if v]
        
        if found_issues:
            logger.warning(f"Found {len(found_issues)} issues: {', '.join(found_issues)}")
        else:
            logger.info("No issues found!")
        
        return issues
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is properly installed"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], 
                capture_output=True, 
                timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _check_cookies(self) -> bool:
        """Check if YouTube cookies are available"""
        cookie_paths = [
            self.project_root / "cookies" / "youtube_cookies.json",
            self.project_root / "data" / "cookies" / "youtube_cookies.json",
            Path("/app/cookies/youtube_cookies.json")
        ]
        
        for path in cookie_paths:
            if path.exists() and path.stat().st_size > 0:
                return True
        return False
    
    def _check_environment(self) -> bool:
        """Check if required environment variables are set"""
        required_vars = ["DISCORD_TOKEN"]
        optional_vars = ["YOUTUBE_API_KEY", "APIFY_API_KEY"]
        
        missing_required = [var for var in required_vars if not os.getenv(var)]
        missing_optional = [var for var in optional_vars if not os.getenv(var)]
        
        if missing_required:
            logger.error(f"Missing required environment variables: {missing_required}")
            return False
        
        if missing_optional:
            logger.warning(f"Missing optional environment variables: {missing_optional}")
        
        return True
    
    def _check_dependencies(self) -> bool:
        """Check if required Python dependencies are installed"""
        required_packages = [
            "discord.py",
            "yt-dlp", 
            "aiohttp",
            "google-api-python-client"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"Missing required packages: {missing_packages}")
            return False
        
        return True
    
    def _check_permissions(self) -> bool:
        """Check if necessary directories have correct permissions"""
        directories = [
            self.project_root / "cookies",
            self.project_root / "data" / "cookies",
            self.project_root / "logs"
        ]
        
        for directory in directories:
            if directory.exists():
                if not os.access(directory, os.R_OK | os.W_OK):
                    logger.error(f"Insufficient permissions for: {directory}")
                    return False
        
        return True
    
    def fix_ffmpeg(self) -> bool:
        """Attempt to fix FFmpeg installation"""
        logger.info("Attempting to fix FFmpeg installation...")
        
        if self._check_ffmpeg():
            logger.info("FFmpeg is already installed")
            return True
        
        # Try different installation methods based on OS
        if sys.platform == "darwin":  # macOS
            return self._install_ffmpeg_macos()
        elif sys.platform.startswith("linux"):
            return self._install_ffmpeg_linux()
        elif sys.platform == "win32":
            return self._install_ffmpeg_windows()
        else:
            logger.error(f"Unsupported platform: {sys.platform}")
            return False
    
    def _install_ffmpeg_macos(self) -> bool:
        """Install FFmpeg on macOS using Homebrew"""
        try:
            # Check if Homebrew is available
            subprocess.run(["brew", "--version"], capture_output=True, check=True)
            
            # Install FFmpeg
            logger.info("Installing FFmpeg using Homebrew...")
            result = subprocess.run(["brew", "install", "ffmpeg"], capture_output=True)
            
            if result.returncode == 0:
                logger.info("FFmpeg installed successfully")
                self.fixes_applied.append("ffmpeg_installed_macos")
                return True
            else:
                logger.error(f"FFmpeg installation failed: {result.stderr.decode()}")
                return False
                
        except subprocess.CalledProcessError:
            logger.error("Homebrew not found. Please install Homebrew first: https://brew.sh/")
            return False
        except Exception as e:
            logger.error(f"Error installing FFmpeg on macOS: {e}")
            return False
    
    def _install_ffmpeg_linux(self) -> bool:
        """Install FFmpeg on Linux using package manager"""
        try:
            # Try apt-get (Ubuntu/Debian)
            logger.info("Attempting to install FFmpeg using apt...")
            result = subprocess.run(
                ["sudo", "apt", "update", "&&", "sudo", "apt", "install", "-y", "ffmpeg"],
                shell=True,
                capture_output=True
            )
            
            if result.returncode == 0:
                logger.info("FFmpeg installed successfully using apt")
                self.fixes_applied.append("ffmpeg_installed_linux_apt")
                return True
            
            # Try yum (CentOS/RHEL)
            logger.info("Attempting to install FFmpeg using yum...")
            result = subprocess.run(
                ["sudo", "yum", "install", "-y", "ffmpeg"],
                capture_output=True
            )
            
            if result.returncode == 0:
                logger.info("FFmpeg installed successfully using yum")
                self.fixes_applied.append("ffmpeg_installed_linux_yum")
                return True
            
            logger.error("Could not install FFmpeg using package managers")
            return False
            
        except Exception as e:
            logger.error(f"Error installing FFmpeg on Linux: {e}")
            return False
    
    def _install_ffmpeg_windows(self) -> bool:
        """Provide instructions for FFmpeg installation on Windows"""
        logger.info("FFmpeg installation on Windows requires manual steps:")
        print("""
        To install FFmpeg on Windows:
        1. Download FFmpeg from: https://ffmpeg.org/download.html#build-windows
        2. Extract the archive to C:\\ffmpeg
        3. Add C:\\ffmpeg\\bin to your PATH environment variable
        4. Restart your command prompt/terminal
        
        Alternatively, use chocolatey:
        choco install ffmpeg
        """)
        self.fixes_applied.append("ffmpeg_instructions_windows")
        return False
    
    def fix_cookies(self) -> bool:
        """Attempt to extract and fix cookie issues"""
        logger.info("Attempting to fix cookie issues...")
        
        # Ensure cookie directories exist
        cookie_dirs = [
            self.project_root / "cookies",
            self.project_root / "data" / "cookies"
        ]
        
        for cookie_dir in cookie_dirs:
            try:
                cookie_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created cookie directory: {cookie_dir}")
            except Exception as e:
                logger.error(f"Could not create cookie directory {cookie_dir}: {e}")
                return False
        
        # Try to run cookie extraction script
        cookie_script = self.project_root / "scripts" / "extract-brave-cookies.py"
        if cookie_script.exists():
            try:
                logger.info("Running cookie extraction script...")
                result = subprocess.run([
                    sys.executable, str(cookie_script)
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    logger.info("Cookie extraction completed successfully")
                    self.fixes_applied.append("cookies_extracted")
                    return True
                else:
                    logger.error(f"Cookie extraction failed: {result.stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                logger.error("Cookie extraction timed out")
                return False
            except Exception as e:
                logger.error(f"Error running cookie extraction: {e}")
                return False
        else:
            logger.warning("Cookie extraction script not found")
            return False
    
    def fix_environment(self) -> bool:
        """Help fix environment variable issues"""
        logger.info("Checking environment configuration...")
        
        env_example = self.project_root / ".env.example"
        env_file = self.project_root / ".env"
        
        if env_example.exists() and not env_file.exists():
            try:
                # Copy .env.example to .env
                with open(env_example, 'r') as src:
                    content = src.read()
                
                with open(env_file, 'w') as dst:
                    dst.write(content)
                
                logger.info("Created .env file from .env.example")
                logger.info("Please edit .env file and add your actual tokens/keys")
                self.fixes_applied.append("env_file_created")
                return True
                
            except Exception as e:
                logger.error(f"Could not create .env file: {e}")
                return False
        
        elif env_file.exists():
            logger.info(".env file already exists")
            return True
        
        else:
            logger.error("No .env.example file found to copy from")
            return False
    
    def fix_dependencies(self) -> bool:
        """Attempt to install missing dependencies"""
        logger.info("Attempting to fix missing dependencies...")
        
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            logger.error("requirements.txt not found")
            return False
        
        try:
            logger.info("Installing dependencies from requirements.txt...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("Dependencies installed successfully")
                self.fixes_applied.append("dependencies_installed")
                return True
            else:
                logger.error(f"Dependency installation failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error installing dependencies: {e}")
            return False
    
    def fix_permissions(self) -> bool:
        """Fix directory permissions"""
        logger.info("Attempting to fix directory permissions...")
        
        directories = [
            self.project_root / "cookies",
            self.project_root / "data" / "cookies",
            self.project_root / "logs"
        ]
        
        fixed_dirs = []
        for directory in directories:
            try:
                if directory.exists():
                    directory.chmod(0o755)
                    fixed_dirs.append(str(directory))
                else:
                    directory.mkdir(parents=True, exist_ok=True)
                    directory.chmod(0o755)
                    fixed_dirs.append(str(directory))
            except Exception as e:
                logger.error(f"Could not fix permissions for {directory}: {e}")
                return False
        
        if fixed_dirs:
            logger.info(f"Fixed permissions for: {', '.join(fixed_dirs)}")
            self.fixes_applied.append("permissions_fixed")
            return True
        
        return True
    
    def fix_all(self) -> bool:
        """Attempt to fix all identified issues"""
        logger.info("Attempting to fix all audio pipeline issues...")
        
        issues = self.check_all_issues()
        all_fixed = True
        
        if issues["dependencies_missing"]:
            all_fixed &= self.fix_dependencies()
        
        if issues["ffmpeg_missing"]:
            all_fixed &= self.fix_ffmpeg()
        
        if issues["environment_incomplete"]:
            all_fixed &= self.fix_environment()
        
        if issues["cookies_missing"]:
            all_fixed &= self.fix_cookies()
        
        if issues["permissions_incorrect"]:
            all_fixed &= self.fix_permissions()
        
        return all_fixed
    
    def generate_fix_report(self) -> str:
        """Generate a report of fixes applied"""
        report = []
        report.append("=" * 60)
        report.append("AUDIO PIPELINE FIX REPORT")
        report.append("=" * 60)
        
        if self.fixes_applied:
            report.append("Fixes Applied:")
            for fix in self.fixes_applied:
                report.append(f"  ✓ {fix.replace('_', ' ').title()}")
        else:
            report.append("No fixes were applied.")
        
        report.append("")
        report.append("Next Steps:")
        report.append("1. Run the diagnostic script to verify fixes:")
        report.append("   python scripts/test-audio-playback.py --test-all")
        report.append("2. If using .env file, make sure to add your actual tokens")
        report.append("3. Test the audio pipeline with a real Discord bot instance")
        
        return "\n".join(report)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Audio Pipeline Issue Fixer for Robustty"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for issues without fixing them"
    )
    
    parser.add_argument(
        "--fix-all",
        action="store_true",
        help="Attempt to fix all identified issues"
    )
    
    parser.add_argument(
        "--fix-ffmpeg",
        action="store_true",
        help="Fix FFmpeg installation issues"
    )
    
    parser.add_argument(
        "--fix-cookies",
        action="store_true",
        help="Fix cookie extraction issues"
    )
    
    parser.add_argument(
        "--fix-environment",
        action="store_true",
        help="Fix environment configuration issues"
    )
    
    parser.add_argument(
        "--fix-dependencies",
        action="store_true",
        help="Fix Python dependency issues"
    )
    
    parser.add_argument(
        "--fix-permissions",
        action="store_true",
        help="Fix directory permission issues"
    )
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        parser.error("Please specify at least one action")
    
    fixer = AudioIssueFixer()
    
    try:
        if args.check:
            issues = fixer.check_all_issues()
            print("\nIssue Summary:")
            for issue, exists in issues.items():
                status = "✗ FOUND" if exists else "✓ OK"
                print(f"  {issue.replace('_', ' ').title()}: {status}")
        
        if args.fix_all:
            success = fixer.fix_all()
            print(f"\nFix All Result: {'✓ SUCCESS' if success else '✗ PARTIAL'}")
        
        if args.fix_ffmpeg:
            success = fixer.fix_ffmpeg()
            print(f"\nFFmpeg Fix Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        if args.fix_cookies:
            success = fixer.fix_cookies()
            print(f"\nCookie Fix Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        if args.fix_environment:
            success = fixer.fix_environment()
            print(f"\nEnvironment Fix Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        if args.fix_dependencies:
            success = fixer.fix_dependencies()
            print(f"\nDependency Fix Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        if args.fix_permissions:
            success = fixer.fix_permissions()
            print(f"\nPermissions Fix Result: {'✓ SUCCESS' if success else '✗ FAILED'}")
        
        # Generate and display report
        if fixer.fixes_applied:
            print("\n" + fixer.generate_fix_report())
            
    except KeyboardInterrupt:
        logger.info("Fix process interrupted by user")
    except Exception as e:
        logger.error(f"Fix process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()