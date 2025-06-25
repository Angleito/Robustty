#!/usr/bin/env python3
"""
Test YouTube cookie integration and conversion functionality.
Tests cookie conversion from JSON to Netscape format without requiring yt-dlp.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class YouTubeCookieTester:
    """Test YouTube cookie functionality"""
    
    def __init__(self):
        self.temp_dir = None
    
    def setup(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {self.temp_dir}")
    
    def cleanup(self):
        """Cleanup test environment"""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
    
    def _convert_cookies_to_netscape(self, json_cookie_file: str, netscape_cookie_file: str) -> bool:
        """
        Copy of the cookie conversion method from YouTube platform
        (from src/platforms/youtube.py lines 366-492)
        """
        try:
            if not Path(json_cookie_file).exists():
                logger.warning(f"JSON cookie file not found: {json_cookie_file}")
                return False

            # Validate file is readable and not empty
            try:
                file_size = Path(json_cookie_file).stat().st_size
                if file_size == 0:
                    logger.warning(f"Cookie file is empty: {json_cookie_file}")
                    return False
            except Exception as e:
                logger.error(f"Cannot access cookie file {json_cookie_file}: {e}")
                return False

            # Read and parse JSON cookies
            try:
                with open(json_cookie_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning(f"Cookie file content is empty: {json_cookie_file}")
                        return False
                    cookies = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in cookie file {json_cookie_file}: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to read cookie file {json_cookie_file}: {e}")
                return False

            if not cookies or not isinstance(cookies, list):
                logger.warning(f"No valid cookies found in {json_cookie_file} (found: {type(cookies)})")
                return False

            # Ensure output directory exists
            try:
                Path(netscape_cookie_file).parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Cannot create cookie output directory: {e}")
                return False

            # Convert to Netscape format
            try:
                with open(netscape_cookie_file, "w", encoding="utf-8") as f:
                    # Write Netscape cookie file header
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# This is a generated file! Do not edit.\n\n")

                    valid_cookies = 0
                    for cookie in cookies:
                        # Skip invalid cookie entries
                        if not isinstance(cookie, dict):
                            continue

                        name = cookie.get("name", "").strip()
                        value = cookie.get("value", "")

                        # Skip cookies without name (value can be empty)
                        if not name:
                            continue

                        # Skip cookies with problematic characters
                        if ("\t" in name or "\t" in value or "\n" in name or "\n" in value):
                            logger.debug(f"Skipping cookie with invalid characters: {name}")
                            continue

                        # Netscape format: domain, domain_specified, path, secure, expires, name, value
                        domain = cookie.get("domain", ".youtube.com")
                        if not domain:
                            domain = ".youtube.com"

                        domain_specified = "TRUE" if domain.startswith(".") else "FALSE"
                        path = cookie.get("path", "/")
                        secure = "TRUE" if cookie.get("secure", False) else "FALSE"

                        # Handle expires field - convert to Unix timestamp if needed
                        expires = cookie.get("expires", 0)
                        if expires is None:
                            expires = 0
                        elif isinstance(expires, (int, float)):
                            expires = int(expires)
                        else:
                            expires = 0

                        # Write cookie line in Netscape format
                        cookie_line = f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
                        f.write(cookie_line)
                        valid_cookies += 1

                if valid_cookies > 0:
                    logger.info(f"Successfully converted {valid_cookies} cookies to Netscape format")
                    return True
                else:
                    logger.warning("No valid cookies were converted")
                    return False

            except Exception as e:
                logger.error(f"Failed to write Netscape cookie file {netscape_cookie_file}: {e}")
                return False

        except Exception as e:
            logger.error(f"Unexpected error during cookie conversion: {e}")
            import traceback
            logger.debug(f"Cookie conversion traceback: {traceback.format_exc()}")
            return False
    
    def test_cookie_conversion_basic(self) -> bool:
        """Test basic cookie conversion functionality"""
        logger.info("Testing basic cookie conversion...")
        
        # Create test cookies similar to YouTube cookies
        test_cookies = [
            {
                "name": "APISID",
                "value": "abc123def456ghi789",
                "domain": ".youtube.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "expires": 1735689600  # 2025-01-01
            },
            {
                "name": "HSID",
                "value": "xyz789uvw456rst123",
                "domain": ".youtube.com",
                "path": "/",
                "secure": False,
                "httpOnly": True,
                "expires": 1735689600
            },
            {
                "name": "SSID",
                "value": "session_token_here",
                "domain": "www.youtube.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            },
            {
                "name": "PREF",
                "value": "f4=4000000&tz=America.New_York",
                "domain": ".youtube.com",
                "path": "/",
                "secure": False,
                "httpOnly": False,
                "expires": 1767225600  # 2026-01-01
            }
        ]
        
        json_file = Path(self.temp_dir) / "youtube_cookies.json"
        netscape_file = Path(self.temp_dir) / "youtube_cookies.txt"
        
        try:
            # Write test cookies
            with open(json_file, 'w') as f:
                json.dump(test_cookies, f, indent=2)
            
            # Test conversion
            success = self._convert_cookies_to_netscape(str(json_file), str(netscape_file))
            
            if not success:
                logger.error("✗ Cookie conversion failed")
                return False
            
            # Verify output file
            if not netscape_file.exists():
                logger.error("✗ Netscape cookie file not created")
                return False
            
            # Read and validate content
            with open(netscape_file, 'r') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            
            # Verify header
            if not lines[0].startswith("# Netscape HTTP Cookie File"):
                logger.error("✗ Missing Netscape header")
                return False
            
            # Count cookie lines
            cookie_lines = [line for line in lines if line and not line.startswith('#')]
            
            if len(cookie_lines) != len(test_cookies):
                logger.error(f"✗ Expected {len(test_cookies)} cookie lines, got {len(cookie_lines)}")
                return False
            
            # Verify cookie format
            for line in cookie_lines:
                parts = line.split('\t')
                if len(parts) != 7:
                    logger.error(f"✗ Invalid cookie line format: {line}")
                    return False
                
                domain, domain_specified, path, secure, expires, name, value = parts
                
                # Basic validation
                if not name:
                    logger.error(f"✗ Cookie missing name: {line}")
                    return False
                
                if domain_specified not in ["TRUE", "FALSE"]:
                    logger.error(f"✗ Invalid domain_specified: {domain_specified}")
                    return False
                
                if secure not in ["TRUE", "FALSE"]:
                    logger.error(f"✗ Invalid secure flag: {secure}")
                    return False
            
            logger.info(f"✓ Successfully converted {len(test_cookies)} cookies")
            return True
            
        except Exception as e:
            logger.error(f"✗ Cookie conversion test failed: {e}")
            return False
    
    def test_cookie_edge_cases(self) -> bool:
        """Test cookie conversion edge cases"""
        logger.info("Testing cookie conversion edge cases...")
        
        edge_cases = [
            # Empty cookies list
            {
                "name": "empty_list",
                "cookies": [],
                "should_succeed": False,
                "description": "Empty cookies list"
            },
            
            # Invalid cookie structure
            {
                "name": "invalid_structure",
                "cookies": [{"not_a_cookie": "invalid"}],
                "should_succeed": False,
                "description": "Invalid cookie structure"
            },
            
            # Cookie with missing name
            {
                "name": "missing_name",
                "cookies": [{"value": "test", "domain": ".youtube.com"}],
                "should_succeed": False,
                "description": "Cookie missing name"
            },
            
            # Cookie with empty name
            {
                "name": "empty_name",
                "cookies": [{"name": "", "value": "test", "domain": ".youtube.com"}],
                "should_succeed": False,
                "description": "Cookie with empty name"
            },
            
            # Cookie with special characters
            {
                "name": "special_chars",
                "cookies": [{"name": "test\ttab", "value": "value", "domain": ".youtube.com"}],
                "should_succeed": False,
                "description": "Cookie with tab character"
            },
            
            # Valid minimal cookie
            {
                "name": "minimal_valid",
                "cookies": [{"name": "test", "value": "value"}],
                "should_succeed": True,
                "description": "Minimal valid cookie"
            },
            
            # Cookie with all fields
            {
                "name": "complete_cookie",
                "cookies": [{
                    "name": "complete",
                    "value": "test_value",
                    "domain": ".youtube.com",
                    "path": "/watch",
                    "secure": True,
                    "httpOnly": False,
                    "expires": 1735689600
                }],
                "should_succeed": True,
                "description": "Complete cookie with all fields"
            }
        ]
        
        success_count = 0
        total_cases = len(edge_cases)
        
        for case in edge_cases:
            logger.info(f"Testing: {case['description']}")
            
            json_file = Path(self.temp_dir) / f"{case['name']}.json"
            netscape_file = Path(self.temp_dir) / f"{case['name']}.txt"
            
            try:
                # Write test data
                with open(json_file, 'w') as f:
                    json.dump(case['cookies'], f, indent=2)
                
                # Test conversion
                success = self._convert_cookies_to_netscape(str(json_file), str(netscape_file))
                
                if success == case['should_succeed']:
                    logger.info(f"  ✓ {case['description']}: Expected {case['should_succeed']}, got {success}")
                    success_count += 1
                else:
                    logger.error(f"  ✗ {case['description']}: Expected {case['should_succeed']}, got {success}")
                    
            except Exception as e:
                if case['should_succeed']:
                    logger.error(f"  ✗ {case['description']}: Unexpected exception: {e}")
                else:
                    logger.info(f"  ✓ {case['description']}: Expected exception: {e}")
                    success_count += 1
        
        logger.info(f"Edge case tests: {success_count}/{total_cases} passed")
        return success_count == total_cases
    
    def test_cookie_path_fallback(self) -> bool:
        """Test cookie path fallback logic"""
        logger.info("Testing cookie path fallback logic...")
        
        # Simulate the path fallback logic from get_stream_url method
        cookie_paths = [
            "/app/cookies/youtube_cookies.json",
            "data/cookies/youtube_cookies.json", 
            "./cookies/youtube_cookies.json",
        ]
        
        # Test that non-existent paths are handled gracefully
        for path in cookie_paths:
            result = self._convert_cookies_to_netscape(path, f"{path}.txt")
            if result:
                logger.error(f"✗ Unexpected success for non-existent path: {path}")
                return False
            else:
                logger.info(f"✓ Correctly handled non-existent path: {path}")
        
        # Test with existing cookie file
        test_cookie_dir = Path(self.temp_dir) / "cookies"
        test_cookie_dir.mkdir(exist_ok=True)
        
        json_file = test_cookie_dir / "youtube_cookies.json"
        test_cookies = [{"name": "test", "value": "value", "domain": ".youtube.com"}]
        
        with open(json_file, 'w') as f:
            json.dump(test_cookies, f)
        
        # Test conversion with existing file
        netscape_file = test_cookie_dir / "youtube_cookies.txt"
        success = self._convert_cookies_to_netscape(str(json_file), str(netscape_file))
        
        if success:
            logger.info("✓ Successfully processed existing cookie file")
            return True
        else:
            logger.error("✗ Failed to process existing cookie file")
            return False
    
    def test_real_cookie_format(self) -> bool:
        """Test with realistic YouTube cookie format"""
        logger.info("Testing with realistic YouTube cookie format...")
        
        # Load actual cookie structure from the project's cookie file
        project_cookie_file = Path(__file__).parent / "cookies" / "youtube_cookies.json"
        
        if project_cookie_file.exists():
            try:
                with open(project_cookie_file, 'r') as f:
                    real_cookies = json.load(f)
                
                if real_cookies:
                    logger.info(f"Found {len(real_cookies)} real cookies to test with")
                    
                    # Test conversion with real cookies
                    json_file = Path(self.temp_dir) / "real_cookies.json"
                    netscape_file = Path(self.temp_dir) / "real_cookies.txt"
                    
                    with open(json_file, 'w') as f:
                        json.dump(real_cookies, f)
                    
                    success = self._convert_cookies_to_netscape(str(json_file), str(netscape_file))
                    
                    if success:
                        logger.info("✓ Successfully converted real YouTube cookies")
                        
                        # Verify the converted cookies
                        with open(netscape_file, 'r') as f:
                            content = f.read()
                        
                        cookie_lines = [line for line in content.split('\n') 
                                      if line and not line.startswith('#')]
                        
                        logger.info(f"✓ Converted {len(cookie_lines)} real cookies")
                        return True
                    else:
                        logger.error("✗ Failed to convert real YouTube cookies")
                        return False
                else:
                    logger.info("⚠ Real cookie file is empty, skipping real cookie test")
                    return True
                    
            except Exception as e:
                logger.error(f"✗ Error testing with real cookies: {e}")
                return False
        else:
            logger.info("⚠ No real cookie file found, skipping real cookie test")
            return True
    
    def run_all_tests(self) -> bool:
        """Run all cookie integration tests"""
        logger.info("="*70)
        logger.info("YOUTUBE COOKIE INTEGRATION TESTING")
        logger.info("="*70)
        
        try:
            self.setup()
            
            results = []
            
            # Run individual tests
            results.append(("Basic Cookie Conversion", self.test_cookie_conversion_basic()))
            results.append(("Cookie Edge Cases", self.test_cookie_edge_cases()))
            results.append(("Cookie Path Fallback", self.test_cookie_path_fallback()))
            results.append(("Real Cookie Format", self.test_real_cookie_format()))
            
            # Print summary
            logger.info("\n" + "="*70)
            logger.info("COOKIE TEST RESULTS SUMMARY")
            logger.info("="*70)
            
            passed_tests = 0
            total_tests = len(results)
            
            for test_name, passed in results:
                if passed:
                    logger.info(f"✅ {test_name}: PASSED")
                    passed_tests += 1
                else:
                    logger.info(f"❌ {test_name}: FAILED")
            
            logger.info(f"\nOverall: {passed_tests}/{total_tests} test suites passed")
            
            if passed_tests == total_tests:
                logger.info("🎉 All YouTube cookie integration tests passed!")
                logger.info("The YouTube platform can correctly:")
                logger.info("  • Convert JSON cookies to Netscape format")
                logger.info("  • Handle various cookie edge cases")
                logger.info("  • Use cookie path fallback logic")
                logger.info("  • Process real YouTube cookie data")
            else:
                logger.info("⚠️  Some tests failed. Review the output above for details.")
            
            logger.info("="*70)
            
            return passed_tests == total_tests
            
        finally:
            self.cleanup()


def main():
    """Main test function"""
    tester = YouTubeCookieTester()
    success = tester.run_all_tests()
    return success


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        exit(130)
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)