# YouTube Language Configuration Options

This document describes the new language behavior configuration options added to the YouTube platform.

## Configuration Options

The following options can be configured in `config/config.yaml` under the `platforms.youtube` section:

### `default_region` (default: "US")
Sets the default region code for YouTube API searches. This affects which regional results are prioritized.

**Environment Variable:** `YOUTUBE_DEFAULT_REGION`
**Examples:** "US", "GB", "ES", "FR", "DE", "JP"

### `default_language` (default: "en") 
Sets the default language code when language detection is disabled or as a fallback.

**Environment Variable:** `YOUTUBE_DEFAULT_LANGUAGE`  
**Examples:** "en", "es", "fr", "de", "ja", "pt"

### `auto_detect_language` (default: true)
Enables or disables automatic language detection from search queries.

**Environment Variable:** `YOUTUBE_AUTO_DETECT_LANGUAGE`
- `true`: Analyze query text to detect language automatically
- `false`: Always use `default_language`

### `force_english_for_english_queries` (default: true)
Controls whether to add English interface language parameter (`hl=en`) for English queries.

**Environment Variable:** `YOUTUBE_FORCE_ENGLISH_FOR_ENGLISH_QUERIES` 
- `true`: Add `hl=en` parameter for English queries to prefer English titles/descriptions
- `false`: Let YouTube use its default interface language

## How It Works

1. **Query Analysis**: When a search is performed, the query text is analyzed to detect if it's in English or another language
2. **Parameter Selection**: Based on the configuration and detected language, appropriate API parameters are set:
   - `regionCode`: Controls regional result preferences
   - `relevanceLanguage`: Influences which language results are prioritized  
   - `hl`: Sets interface language for result titles and descriptions (when applicable)
3. **API Request**: The YouTube API is called with these parameters to get appropriately localized results

## Example Configurations

### Default (English-focused)
```yaml
platforms:
  youtube:
    default_region: "US"
    default_language: "en"
    auto_detect_language: true
    force_english_for_english_queries: true
```

### Spanish-focused
```yaml
platforms:
  youtube:
    default_region: "ES" 
    default_language: "es"
    auto_detect_language: false
    force_english_for_english_queries: false
```

### International (auto-detect)
```yaml
platforms:
  youtube:
    default_region: "US"
    default_language: "en" 
    auto_detect_language: true
    force_english_for_english_queries: false
```

## Query Examples

With default configuration:
- "how to play guitar" → English results with English interface
- "música brasileira" → Portuguese/Brazilian results with auto language
- "rock music" → English results with English interface

With Spanish-focused configuration:
- "how to play guitar" → Spanish results with Spanish interface
- "música brasileira" → Spanish results with Spanish interface  
- "rock music" → Spanish results with Spanish interface

## Implementation Details

- Language detection uses ASCII content analysis and common English word patterns
- Both API searches and yt-dlp fallback searches respect these settings
- Configuration is loaded during platform initialization
- Settings can be overridden via environment variables for deployment flexibility

## Backward Compatibility

All options have sensible defaults that maintain the existing behavior of preferring English results for English queries while allowing non-English queries to return results in their original language.