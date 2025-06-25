#!/usr/bin/env python3
"""
Test runner for YouTube platform fallback functionality

This script runs all fallback-related tests and provides detailed reporting
on the test results. It can be used for continuous integration or manual testing.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any


def run_test_suite(test_file: str, markers: List[str] = None, verbose: bool = True) -> Dict[str, Any]:
    """Run a specific test suite and return results"""
    cmd = ["python", "-m", "pytest", test_file]
    
    if verbose:
        cmd.append("-v")
    
    if markers:
        for marker in markers:
            cmd.extend(["-m", marker])
    
    # Add coverage if available
    try:
        import coverage
        cmd.extend(["--cov=src", "--cov-report=term-missing"])
    except ImportError:
        pass
    
    print(f"Running: {' '.join(cmd)}")
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        end_time = time.time()
        
        return {
            "test_file": test_file,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": end_time - start_time,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "test_file": test_file,
            "returncode": -1,
            "stdout": "",
            "stderr": "Test timed out after 300 seconds",
            "duration": 300,
            "success": False
        }


def print_test_results(results: List[Dict[str, Any]]):
    """Print formatted test results"""
    print("\n" + "="*80)
    print("FALLBACK FUNCTIONALITY TEST RESULTS")
    print("="*80)
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])
    total_duration = sum(r["duration"] for r in results)
    
    print(f"Total test suites: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    print(f"Total duration: {total_duration:.2f} seconds")
    print()
    
    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        duration = result["duration"]
        test_name = Path(result["test_file"]).stem
        
        print(f"{status} {test_name:<40} ({duration:.2f}s)")
        
        if not result["success"]:
            print(f"  Error output:")
            error_lines = result["stderr"].split('\n')[:10]  # First 10 lines
            for line in error_lines:
                if line.strip():
                    print(f"    {line}")
            print()
    
    print("="*80)


def run_comprehensive_tests(args):
    """Run comprehensive fallback tests"""
    test_files = [
        "tests/test_platforms/test_youtube_fallback_comprehensive.py",
        "tests/test_services/test_platform_fallback_manager.py",
    ]
    
    if args.include_integration:
        test_files.append("tests/integration/test_youtube_fallback_integration.py")
    
    results = []
    
    for test_file in test_files:
        if not Path(test_file).exists():
            print(f"Warning: Test file {test_file} does not exist, skipping...")
            continue
        
        markers = []
        if args.integration_only and "integration" in test_file:
            markers.append("integration")
        elif args.unit_only and "integration" not in test_file:
            markers.append("unit")
        
        result = run_test_suite(test_file, markers=markers, verbose=args.verbose)
        results.append(result)
        
        # Print immediate feedback
        status = "✅" if result["success"] else "❌"
        print(f"{status} {Path(test_file).stem} completed in {result['duration']:.2f}s")
        
        if not result["success"] and args.fail_fast:
            print("Stopping due to test failure (--fail-fast)")
            break
    
    return results


def run_specific_test_scenarios(args):
    """Run specific test scenarios"""
    scenarios = {
        "url_processing": {
            "file": "tests/test_platforms/test_youtube_fallback_comprehensive.py",
            "class": "TestDirectYouTubeURLProcessing"
        },
        "api_quota": {
            "file": "tests/test_platforms/test_youtube_fallback_comprehensive.py", 
            "class": "TestYtDlpFallbackFunctionality"
        },
        "cookies": {
            "file": "tests/test_platforms/test_youtube_fallback_comprehensive.py",
            "class": "TestCookieEnhancedAuthentication"
        },
        "degradation": {
            "file": "tests/test_platforms/test_youtube_fallback_comprehensive.py",
            "class": "TestGracefulDegradation"
        },
        "manager": {
            "file": "tests/test_services/test_platform_fallback_manager.py",
            "class": None  # Run entire file
        },
        "integration": {
            "file": "tests/integration/test_youtube_fallback_integration.py",
            "class": None
        }
    }
    
    results = []
    
    for scenario_name in args.scenarios:
        if scenario_name not in scenarios:
            print(f"Unknown scenario: {scenario_name}")
            continue
        
        scenario = scenarios[scenario_name]
        test_file = scenario["file"]
        
        if not Path(test_file).exists():
            print(f"Warning: Test file {test_file} does not exist, skipping {scenario_name}...")
            continue
        
        cmd_args = [test_file]
        if scenario["class"]:
            cmd_args.append(f"-k {scenario['class']}")
        
        # Build pytest command
        cmd = ["python", "-m", "pytest"] + cmd_args
        if args.verbose:
            cmd.append("-v")
        
        print(f"Running scenario '{scenario_name}': {' '.join(cmd)}")
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        end_time = time.time()
        
        results.append({
            "test_file": f"{scenario_name} ({test_file})",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": end_time - start_time,
            "success": result.returncode == 0
        })
        
        status = "✅" if result.returncode == 0 else "❌"
        print(f"{status} Scenario '{scenario_name}' completed in {end_time - start_time:.2f}s")
    
    return results


def validate_test_environment():
    """Validate that the test environment is properly set up"""
    print("Validating test environment...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    
    # Check required packages
    required_packages = ["pytest", "src.platforms", "src.services"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        return False
    
    # Check test files exist
    test_files = [
        "tests/test_platforms/test_youtube_fallback_comprehensive.py",
        "tests/test_services/test_platform_fallback_manager.py",
        "tests/integration/test_youtube_fallback_integration.py",
    ]
    
    missing_files = [f for f in test_files if not Path(f).exists()]
    if missing_files:
        print(f"❌ Missing test files: {', '.join(missing_files)}")
        return False
    
    print("✅ Test environment is valid")
    return True


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(
        description="Run YouTube platform fallback functionality tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all fallback tests
  python tests/run_fallback_tests.py
  
  # Run only unit tests
  python tests/run_fallback_tests.py --unit-only
  
  # Run specific scenarios
  python tests/run_fallback_tests.py --scenarios url_processing api_quota
  
  # Run with integration tests
  python tests/run_fallback_tests.py --include-integration
  
  # Run quietly and stop on first failure
  python tests/run_fallback_tests.py --quiet --fail-fast
        """
    )
    
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=["url_processing", "api_quota", "cookies", "degradation", "manager", "integration"],
        help="Run specific test scenarios"
    )
    
    parser.add_argument(
        "--include-integration",
        action="store_true",
        help="Include integration tests (may require external dependencies)"
    )
    
    parser.add_argument(
        "--integration-only",
        action="store_true",
        help="Run only integration tests"
    )
    
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="Run only unit tests (exclude integration tests)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose test output (default: True)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Quiet mode - minimal output"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first test failure"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate test environment, don't run tests"
    )
    
    args = parser.parse_args()
    
    # Handle quiet mode
    if args.quiet:
        args.verbose = False
    
    # Validate environment
    if not validate_test_environment():
        sys.exit(1)
    
    if args.validate_only:
        print("✅ Test environment validation complete")
        sys.exit(0)
    
    print("Starting fallback functionality tests...")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {Path.cwd()}")
    print()
    
    # Run tests based on arguments
    if args.scenarios:
        results = run_specific_test_scenarios(args)
    else:
        results = run_comprehensive_tests(args)
    
    # Print results
    print_test_results(results)
    
    # Exit with appropriate code
    if all(r["success"] for r in results):
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()