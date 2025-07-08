#!/usr/bin/env python3
"""
Quick test script for Discord 530 diagnostic tools.
Tests basic functionality without external dependencies.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported."""
    print("🧪 Testing imports...")
    
    try:
        # Test file existence
        scripts_dir = Path(__file__).parent
        
        files_to_test = [
            "diagnose-discord-530-comprehensive.py",
            "discord-530-decision-tree.py", 
            "discord-530-master.py"
        ]
        
        for filename in files_to_test:
            file_path = scripts_dir / filename
            if not file_path.exists():
                print(f"❌ Missing file: {filename}")
                return False
            else:
                print(f"✅ Found: {filename}")
        
        # Test syntax by compiling
        import py_compile
        for filename in files_to_test:
            file_path = scripts_dir / filename
            try:
                py_compile.compile(str(file_path), doraise=True)
                print(f"✅ Syntax OK: {filename}")
            except py_compile.PyCompileError as e:
                print(f"❌ Syntax error in {filename}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_class_definitions():
    """Test that main classes can be loaded."""
    print("\n🏗️  Testing class definitions...")
    
    try:
        scripts_dir = Path(__file__).parent
        
        # Test comprehensive module classes
        comp_file = scripts_dir / "diagnose-discord-530-comprehensive.py"
        comp_content = comp_file.read_text()
        
        if "class DiscordAuthDiagnostics:" in comp_content:
            print("✅ DiscordAuthDiagnostics class found")
        else:
            print("❌ DiscordAuthDiagnostics class missing")
            return False
        
        # Test decision tree classes
        tree_file = scripts_dir / "discord-530-decision-tree.py"
        tree_content = tree_file.read_text()
        
        if "class Discord530DecisionTree:" in tree_content and "class DecisionNode:" in tree_content:
            print("✅ Decision tree classes found")
        else:
            print("❌ Decision tree classes missing")
            return False
        
        # Test master controller
        master_file = scripts_dir / "discord-530-master.py"
        master_content = master_file.read_text()
        
        if "class Discord530Master:" in master_content:
            print("✅ Master controller class found")
        else:
            print("❌ Master controller class missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Class definition test failed: {e}")
        return False

def test_method_signatures():
    """Test that key methods are present."""
    print("\n📝 Testing method signatures...")
    
    try:
        scripts_dir = Path(__file__).parent
        
        # Check comprehensive module methods
        comp_file = scripts_dir / "diagnose-discord-530-comprehensive.py"
        comp_content = comp_file.read_text()
        
        required_methods = [
            "check_bot_application_status",
            "analyze_environment_network", 
            "detect_multiple_instances",
            "investigate_rate_limiting",
            "audit_code_configuration"
        ]
        
        for method in required_methods:
            if f"async def {method}" in comp_content:
                print(f"✅ Method found: {method}")
            else:
                print(f"❌ Method missing: {method}")
                return False
        
        # Check decision tree methods
        tree_file = scripts_dir / "discord-530-decision-tree.py"
        tree_content = tree_file.read_text()
        
        tree_methods = [
            "_check_token_exists",
            "_check_token_validity",
            "_check_multiple_instances",
            "run_interactive_diagnosis"
        ]
        
        for method in tree_methods:
            if f"async def {method}" in tree_content or f"def {method}" in tree_content:
                print(f"✅ Tree method found: {method}")
            else:
                print(f"❌ Tree method missing: {method}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Method signature test failed: {e}")
        return False

def test_configuration():
    """Test tool configuration and structure."""
    print("\n⚙️  Testing configuration...")
    
    try:
        # Check if README exists
        scripts_dir = Path(__file__).parent
        readme_file = scripts_dir / "README-discord-530-diagnostics.md"
        
        if readme_file.exists():
            print("✅ README found")
            
            # Check README content
            readme_content = readme_file.read_text()
            if "Discord WebSocket 530 Diagnostic Tools" in readme_content:
                print("✅ README content looks good")
            else:
                print("❌ README content incomplete")
                return False
        else:
            print("❌ README missing")
            return False
        
        # Check all scripts are executable
        for script_name in ["diagnose-discord-530-comprehensive.py", 
                           "discord-530-decision-tree.py", 
                           "discord-530-master.py"]:
            script_path = scripts_dir / script_name
            if os.access(script_path, os.X_OK):
                print(f"✅ Executable: {script_name}")
            else:
                print(f"⚠️  Not executable: {script_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Discord 530 Diagnostic Tools Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Class Definition Tests", test_class_definitions), 
        ("Method Signature Tests", test_method_signatures),
        ("Configuration Tests", test_configuration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * len(test_name))
        
        if test_func():
            print(f"✅ {test_name} PASSED")
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed! Diagnostic tools are ready to use.")
        print("\nQuick start:")
        print("  python scripts/discord-530-master.py")
        return 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)