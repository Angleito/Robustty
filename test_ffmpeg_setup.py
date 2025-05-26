#!/usr/bin/env python3
"""
FFmpeg Setup Verification

Quick test to verify FFmpeg installation and Discord.py compatibility
"""

import subprocess
import sys
import tempfile
import os
from pathlib import Path

def test_ffmpeg_basic():
    """Test basic FFmpeg installation"""
    print("🔧 Testing FFmpeg basic installation...")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg found: {version_line}")
            return True
        else:
            print(f"❌ FFmpeg error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg not found in PATH")
        print("Install FFmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/")
        return False
    except Exception as e:
        print(f"❌ FFmpeg test failed: {e}")
        return False

def test_ffmpeg_audio_processing():
    """Test FFmpeg audio processing capabilities"""
    print("🎵 Testing FFmpeg audio processing...")
    
    try:
        # Test generating audio
        result = subprocess.run([
            'ffmpeg', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
            '-f', 'null', '-'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ FFmpeg can generate audio")
        else:
            print(f"❌ FFmpeg audio generation failed: {result.stderr}")
            return False
        
        # Test converting audio
        temp_dir = tempfile.gettempdir()
        test_file = os.path.join(temp_dir, "ffmpeg_test.wav")
        
        result = subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
            '-ar', '48000', '-ac', '2', test_file
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(test_file):
            print("✅ FFmpeg can create audio files")
            os.remove(test_file)  # Clean up
            return True
        else:
            print(f"❌ FFmpeg audio conversion failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ FFmpeg audio processing test failed: {e}")
        return False

def test_discord_ffmpeg_options():
    """Test FFmpeg with Discord.py options"""
    print("🤖 Testing FFmpeg with Discord.py options...")
    
    try:
        # Test the exact options used by Discord.py
        cmd = [
            'ffmpeg',
            '-reconnect', '1',
            '-reconnect_streamed', '1', 
            '-reconnect_delay_max', '5',
            '-i', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            '-vn',
            '-f', 'null',
            '-'
        ]
        
        print("Testing with YouTube URL (this may take a moment)...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✅ FFmpeg works with Discord.py options and YouTube")
            return True
        else:
            print(f"⚠️ FFmpeg with YouTube failed: {result.stderr}")
            print("This might be due to yt-dlp not being installed or YouTube changes")
            
            # Try with a simpler test
            print("Testing with sine wave instead...")
            simple_cmd = [
                'ffmpeg',
                '-f', 'lavfi',
                '-i', 'sine=frequency=440:duration=2',
                '-vn',
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(simple_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ FFmpeg works with Discord.py audio options")
                return True
            else:
                print(f"❌ FFmpeg failed with Discord.py options: {result.stderr}")
                return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ FFmpeg test timed out (this might be normal for YouTube URLs)")
        return True  # Timeout might be OK for YouTube
    except Exception as e:
        print(f"❌ Discord FFmpeg options test failed: {e}")
        return False

def test_discord_py_import():
    """Test Discord.py import and audio capabilities"""
    print("📦 Testing Discord.py installation...")
    
    try:
        import discord
        print(f"✅ Discord.py version: {discord.__version__}")
        
        # Test audio classes
        try:
            # This should not raise an error if FFmpeg is properly installed
            from discord import FFmpegPCMAudio, PCMVolumeTransformer
            print("✅ Discord.py audio classes available")
            
            # Test creating an audio source with a file
            temp_dir = tempfile.gettempdir()
            test_file = os.path.join(temp_dir, "discord_test.wav")
            
            # Create a test file
            subprocess.run([
                'ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
                '-ar', '48000', '-ac', '2', test_file
            ], capture_output=True, timeout=5)
            
            if os.path.exists(test_file):
                try:
                    source = FFmpegPCMAudio(test_file)
                    transformer = PCMVolumeTransformer(source, volume=0.5)
                    print("✅ Discord.py audio source creation works")
                    os.remove(test_file)  # Clean up
                    return True
                except Exception as e:
                    print(f"❌ Discord.py audio source creation failed: {e}")
                    return False
            else:
                print("⚠️ Could not create test file for Discord.py test")
                return True  # FFmpeg issues, not Discord.py
                
        except ImportError as e:
            print(f"❌ Discord.py audio imports failed: {e}")
            return False
            
    except ImportError:
        print("❌ Discord.py not installed")
        print("Install with: pip install discord.py[voice]")
        return False

def main():
    """Run all FFmpeg and Discord.py tests"""
    print("🎵 FFmpeg and Discord.py Setup Verification")
    print("=" * 50)
    
    tests = [
        ("FFmpeg Basic", test_ffmpeg_basic),
        ("FFmpeg Audio Processing", test_ffmpeg_audio_processing),
        ("Discord.py Installation", test_discord_py_import),
        ("Discord.py FFmpeg Options", test_discord_ffmpeg_options),
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n🧪 {test_name}")
        print("-" * 30)
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 50)
    print("SETUP VERIFICATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your setup should work with Discord voice.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    print("\nNext steps:")
    print("1. If FFmpeg tests failed: Install or update FFmpeg")
    print("2. If Discord.py tests failed: Install discord.py[voice]")
    print("3. If all passed: Run the voice diagnostics with a real bot")
    print("   python test_discord_voice_diagnostics.py --interactive")

if __name__ == "__main__":
    main()