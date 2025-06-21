# Test Organization

This document describes the test structure for the Robustty Discord bot project.

## Test Directory Structure

```
tests/
├── integration/                # End-to-end and integration tests
│   ├── test_audio_system.py   # Comprehensive audio system integration test
│   ├── test_search_to_stream.py # Full search-to-stream workflow test
│   ├── test_voice_integration.py # Discord voice connection diagnostics
│   └── test_rumble_integration.py # Rumble platform integration test
├── test_bot/                   # Bot-specific functionality tests
│   ├── test_admin_cog.py
│   ├── test_commands.py
│   └── ...
├── test_extractors/            # Cookie and data extraction tests
│   ├── test_cookie_extraction.py # Cookie extraction functionality
│   ├── test_cross_platform_cookies.py
│   └── ...
├── test_platforms/             # Platform-specific tests
│   ├── test_youtube_streaming.py # YouTube streaming and cookie integration
│   ├── test_rumble_integration.py # Rumble platform integration
│   ├── test_odysee.py         # Odysee platform tests
│   └── ...
└── test_services/              # Service layer tests
    ├── test_queue_system.py    # Queue management system tests
    ├── test_cookie_manager.py  # Cookie manager integration
    ├── test_cache_manager.py
    └── ...
```

## Test Categories

### Integration Tests (`tests/integration/`)
These tests verify that multiple components work together correctly:

- **test_audio_system.py**: Comprehensive test of the entire audio pipeline from YouTube search to Discord playback
- **test_search_to_stream.py**: End-to-end workflow testing search-to-stream functionality
- **test_voice_integration.py**: Discord voice connection diagnostics and testing
- **test_rumble_integration.py**: Rumble platform integration testing

### Platform Tests (`tests/test_platforms/`)
These tests focus on individual platform implementations:

- **test_youtube_streaming.py**: YouTube platform with streaming fixes and cookie integration
- **test_rumble_integration.py**: Rumble platform integration and URL handling
- **test_odysee.py**: Odysee platform functionality

### Service Tests (`tests/test_services/`)
These tests verify service layer components:

- **test_queue_system.py**: Audio queue management and skip functionality
- **test_cookie_manager.py**: Cookie management service integration

### Extractor Tests (`tests/test_extractors/`)
These tests verify data extraction functionality:

- **test_cookie_extraction.py**: Cross-platform cookie extraction functionality

## Running Tests

### All Tests
```bash
pytest tests/
```

### Specific Categories
```bash
# Integration tests only
pytest tests/integration/ -v

# Platform-specific tests
pytest tests/test_platforms/ -v

# Service tests
pytest tests/test_services/ -v

# Extractor tests
pytest tests/test_extractors/ -v
```

### Specific Platform Tests
```bash
# YouTube tests only
pytest tests/test_platforms/ -k youtube -v

# Rumble tests only
pytest tests/test_platforms/ -k rumble -v
```

### With Markers
```bash
# Integration tests requiring external APIs
pytest tests/ -m integration -v

# Unit tests only
pytest tests/ -m unit -v
```

## Test Cleanup (January 2025)

The following test files were removed during cleanup as they were duplicates, debugging scripts, or superseded by better tests:

### Removed Files:
- `test_env.py` - Environment debugging script
- `test_debug_cookies.py`, `test_simple_cookies.py`, `test_specific_browser.py` - Cookie debugging scripts
- `test_audio_simple.py`, `test_audio_fix.py`, `test_ffmpeg_setup.py` - Basic/duplicate audio tests
- `test_youtube.py`, `test_youtube_search.py`, `test_ytdlp.py` - Basic YouTube tests (superseded by streaming test)
- `test_youtube_cookie_integration.py` - Superseded by `test_youtube_streaming.py`
- `test_stream_service.py`, `test_stream_direct.py` - Development-specific streaming tests
- `test_streaming_fixes.py`, `test_voice_fix.py` - One-off fix tests

### Kept and Organized:
- Comprehensive integration tests moved to `tests/integration/`
- Platform-specific tests moved to `tests/test_platforms/`
- Service tests moved to `tests/test_services/`
- Extractor tests moved to `tests/test_extractors/`

This organization reduces test file clutter from 23+ files to 8 well-organized, non-duplicate test files while preserving all essential functionality.