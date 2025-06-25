# YouTube Language Preference Testing

This document describes the test suite for validating YouTube language preference functionality in the Robustty Discord bot.

## Overview

The language preference system automatically detects the language of search queries and configures YouTube API parameters and yt-dlp settings to return results in the appropriate language and region.

## Test Files

### 1. Core Test Suite: `tests/test_platforms/test_youtube_language_preferences.py`

**Comprehensive test suite covering all language preference functionality.**

#### Test Classes:

- **`TestLanguageDetection`**: Tests the core language detection functionality
  - English, Spanish, French, German, Japanese query detection
  - URL handling (should skip language detection)
  - Language detection enable/disable configuration

- **`TestAPIParameterGeneration`**: Tests API parameter mapping
  - Correct regionCode, relevanceLanguage, and hl parameters
  - Fallback to English for unknown languages

- **`TestYtDlpLanguageConfiguration`**: Tests yt-dlp configuration
  - Accept-Language headers for non-English queries
  - No extra headers for English queries

- **`TestIntegratedLanguageSearch`**: Tests end-to-end search flow
  - API parameter integration
  - yt-dlp fallback respects language preferences
  - URL queries bypass language detection

- **`TestEdgeCases`**: Edge case handling
  - Empty queries, mixed languages, special characters
  - Exception handling for language detection failures

- **`TestConfigurationOptions`**: Configuration flexibility
  - Custom default languages and regions
  - Language detection enable/disable

#### Running the Tests:
```bash
# Run all language preference tests
python -m pytest tests/test_platforms/test_youtube_language_preferences.py -v

# Run specific test class
python -m pytest tests/test_platforms/test_youtube_language_preferences.py::TestLanguageDetection -v

# Run with coverage
python -m pytest tests/test_platforms/test_youtube_language_preferences.py --cov=src.platforms.youtube
```

### 2. Integration Tests: `tests/test_platforms/test_youtube_language_integration.py`

**Integration tests using real language detection libraries.**

Requires `langdetect` library:
```bash
pip install langdetect
```

#### Features:
- Real language detection using `langdetect` library
- Extended language support (Korean, Chinese, Portuguese, Italian, Russian, Arabic)
- More realistic language detection scenarios
- Integration with actual language detection algorithms

#### Running Integration Tests:
```bash
# Install langdetect first
pip install langdetect

# Run integration tests only
python -m pytest tests/test_platforms/test_youtube_language_integration.py -v -m integration

# Run manual language detection test
python tests/test_platforms/test_youtube_language_integration.py
```

### 3. Demo Script: `test_language_detection_demo.py`

**Interactive demonstration of language preference functionality.**

#### Features:
- Visual demonstration of language detection
- Shows API parameters for different languages
- Demonstrates yt-dlp header configuration
- Tests various query types and edge cases

#### Running the Demo:
```bash
python test_language_detection_demo.py
```

## Test Scenarios Covered

### 1. English Queries
- **Input**: `"popular music"`, `"best songs 2024"`
- **Expected**: US region, English language settings
- **API Params**: `regionCode=US`, `relevanceLanguage=en`, `hl=en`
- **yt-dlp**: No special headers

### 2. Non-English Queries

#### Spanish:
- **Input**: `"música popular"`, `"reggaeton nuevo"`
- **Expected**: Spain region, Spanish language settings
- **API Params**: `regionCode=ES`, `relevanceLanguage=es`, `hl=es`
- **yt-dlp**: `Accept-Language: es-ES,es;q=0.9,en;q=0.8`

#### French:
- **Input**: `"musique française"`, `"chansons populaires"`
- **Expected**: France region, French language settings
- **API Params**: `regionCode=FR`, `relevanceLanguage=fr`, `hl=fr`
- **yt-dlp**: `Accept-Language: fr-FR,fr;q=0.9,en;q=0.8`

#### German:
- **Input**: `"deutsche musik"`, `"klassische musik"`
- **Expected**: Germany region, German language settings
- **API Params**: `regionCode=DE`, `relevanceLanguage=de`, `hl=de`
- **yt-dlp**: `Accept-Language: de-DE,de;q=0.9,en;q=0.8`

### 3. Direct URLs
- **Input**: `"https://www.youtube.com/watch?v=dQw4w9WgXcQ"`
- **Expected**: Always default to English settings (no language bias)
- **Behavior**: Language detection is bypassed for URLs

### 4. Fallback yt-dlp Search
- **Scenario**: When YouTube API quota is exceeded or no API key available
- **Expected**: yt-dlp search respects the same language preferences
- **Configuration**: Language-appropriate Accept-Language headers

### 5. Edge Cases
- **Empty queries**: Default to English
- **Very short queries** (< 3 characters): Default to English
- **Mixed language queries**: Prioritize non-English language detection
- **Language detection failures**: Graceful fallback to English

## Configuration Options

### Basic Configuration:
```python
config = {
    "enable_language_detection": True,
    "default_language": "en",
    "default_region": "US"
}
```

### Language-Region Mapping:
| Language | Region Code | Example Country |
|----------|-------------|-----------------|
| en       | US          | United States   |
| es       | ES          | Spain           |
| fr       | FR          | France          |
| de       | DE          | Germany         |
| ja       | JP          | Japan           |
| ko       | KR          | South Korea     |
| zh       | CN          | China           |
| pt       | BR          | Brazil          |
| it       | IT          | Italy           |
| ru       | RU          | Russia          |
| ar       | SA          | Saudi Arabia    |

## Implementation Requirements

To implement this functionality in the actual YouTube platform:

### 1. Add Language Detection Dependency:
```bash
pip install langdetect
```

### 2. Extend YouTubePlatform Class:
```python
class YouTubePlatform(VideoPlatform):
    def _detect_query_language(self, query: str) -> str:
        # Language detection implementation
        
    def _get_api_parameters_for_language(self, language: str) -> Dict[str, str]:
        # API parameter generation
        
    def _get_enhanced_ytdlp_config_with_language(self, language: str) -> Dict[str, Any]:
        # yt-dlp configuration with language headers
```

### 3. Update Search Methods:
- Modify `search_videos()` to detect language and set API parameters
- Update `_search_with_ytdlp()` to use language-appropriate headers
- Ensure URL handling bypasses language detection

### 4. Configuration Updates:
```yaml
# config/config.yaml
platforms:
  youtube:
    enable_language_detection: true
    default_language: "en"
    default_region: "US"
```

## Benefits

1. **Better User Experience**: Users get results in their query language
2. **Accurate Results**: Region-appropriate content recommendations
3. **Fallback Compatibility**: yt-dlp respects same language preferences
4. **No URL Bias**: Direct URLs are not affected by language settings
5. **Graceful Degradation**: Falls back to English on detection errors

## Testing Best Practices

1. **Run All Test Suites**: Ensure comprehensive coverage
2. **Test Multiple Languages**: Verify each supported language works correctly
3. **Test Edge Cases**: Empty queries, special characters, mixed languages
4. **Integration Testing**: Use real language detection when possible
5. **Demo Validation**: Run demo script to visualize behavior

## Troubleshooting

### Common Issues:

1. **Language Detection Not Working**:
   - Ensure `langdetect` is installed
   - Check that `enable_language_detection` is `True`
   - Verify query length (< 3 chars defaults to English)

2. **Wrong Region Selected**:
   - Check language-region mapping configuration
   - Verify language detection accuracy

3. **Tests Failing**:
   - Install test dependencies: `pip install pytest pytest-asyncio`
   - For integration tests: `pip install langdetect`
   - Check mock configurations match expected behavior

4. **yt-dlp Headers Not Applied**:
   - Verify `_get_enhanced_ytdlp_config_with_language()` implementation
   - Check that English queries don't add unnecessary headers