"""
Integration test for YouTube language preference functionality with real language detection.

This test file demonstrates how to integrate real language detection libraries
and can be used when the actual implementation is added to the YouTube platform.

To run these tests, install a language detection library:
pip install langdetect

Note: This test is marked as integration and may require network access or
external dependencies.
"""

import pytest
from unittest.mock import Mock, patch

from src.platforms.youtube import YouTubePlatform


# Skip these tests if langdetect is not available
langdetect = pytest.importorskip("langdetect", reason="langdetect library not installed")
from langdetect import detect, DetectorFactory


class RealLanguageAwareYouTubePlatform(YouTubePlatform):
    """YouTube platform with real language detection"""
    
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self.enable_language_detection = config.get("enable_language_detection", True)
        self.default_region = config.get("default_region", "US")
        self.default_language = config.get("default_language", "en")
        
        # Set random seed for consistent results in langdetect
        DetectorFactory.seed = 0
    
    def _detect_query_language(self, query: str) -> str:
        """Detect the language of the search query using langdetect"""
        if not self.enable_language_detection:
            return self.default_language
        
        # Skip language detection for URLs
        if self.is_platform_url(query):
            return self.default_language
        
        # Skip for very short queries
        if len(query.strip()) < 3:
            return self.default_language
        
        try:
            detected_lang = detect(query)
            # Map langdetect codes to our supported languages
            lang_mapping = {
                'en': 'en',
                'es': 'es', 
                'fr': 'fr',
                'de': 'de',
                'ja': 'ja',
                'ko': 'ko',
                'zh-cn': 'zh',
                'zh': 'zh',
                'pt': 'pt',
                'it': 'it',
                'ru': 'ru',
                'ar': 'ar'
            }
            
            return lang_mapping.get(detected_lang, self.default_language)
            
        except Exception as e:
            # Fall back to default on any error
            return self.default_language
    
    def _get_api_parameters_for_language(self, language: str) -> dict:
        """Get YouTube API parameters based on detected language"""
        language_config = {
            'en': {'regionCode': 'US', 'relevanceLanguage': 'en', 'hl': 'en'},
            'es': {'regionCode': 'ES', 'relevanceLanguage': 'es', 'hl': 'es'},
            'fr': {'regionCode': 'FR', 'relevanceLanguage': 'fr', 'hl': 'fr'},
            'de': {'regionCode': 'DE', 'relevanceLanguage': 'de', 'hl': 'de'},
            'ja': {'regionCode': 'JP', 'relevanceLanguage': 'ja', 'hl': 'ja'},
            'ko': {'regionCode': 'KR', 'relevanceLanguage': 'ko', 'hl': 'ko'},
            'zh': {'regionCode': 'CN', 'relevanceLanguage': 'zh', 'hl': 'zh'},
            'pt': {'regionCode': 'BR', 'relevanceLanguage': 'pt', 'hl': 'pt'},
            'it': {'regionCode': 'IT', 'relevanceLanguage': 'it', 'hl': 'it'},
            'ru': {'regionCode': 'RU', 'relevanceLanguage': 'ru', 'hl': 'ru'},
            'ar': {'regionCode': 'SA', 'relevanceLanguage': 'ar', 'hl': 'ar'},
        }
        
        return language_config.get(language, language_config['en'])


@pytest.fixture
def real_youtube_platform():
    """Create YouTube platform with real language detection"""
    config = {
        "enabled": True,
        "api_key": "test_api_key", 
        "enable_language_detection": True,
        "default_region": "US",
        "default_language": "en"
    }
    return RealLanguageAwareYouTubePlatform("youtube", config)


@pytest.mark.integration
class TestRealLanguageDetection:
    """Test language detection with real langdetect library"""
    
    def test_english_detection(self, real_youtube_platform):
        """Test English query detection"""
        queries = [
            "popular music videos",
            "best songs of 2024",
            "top music hits",
            "latest pop songs"
        ]
        
        for query in queries:
            lang = real_youtube_platform._detect_query_language(query)
            assert lang == 'en', f"Query '{query}' should be detected as English"
    
    def test_spanish_detection(self, real_youtube_platform):
        """Test Spanish query detection"""
        queries = [
            "música popular",
            "canciones románticas",
            "reggaeton nuevo",
            "música latina 2024"
        ]
        
        for query in queries:
            lang = real_youtube_platform._detect_query_language(query)
            assert lang == 'es', f"Query '{query}' should be detected as Spanish"
    
    def test_french_detection(self, real_youtube_platform):
        """Test French query detection"""
        queries = [
            "musique française",
            "chansons populaires",
            "musique classique",
            "artistes français"
        ]
        
        for query in queries:
            lang = real_youtube_platform._detect_query_language(query)
            assert lang == 'fr', f"Query '{query}' should be detected as French"
    
    def test_german_detection(self, real_youtube_platform):
        """Test German query detection"""
        queries = [
            "deutsche musik",
            "klassische musik",
            "beliebte lieder",
            "neue deutsche musik"
        ]
        
        for query in queries:
            lang = real_youtube_platform._detect_query_language(query)
            assert lang == 'de', f"Query '{query}' should be detected as German"
    
    def test_short_query_defaults(self, real_youtube_platform):
        """Test that very short queries default to English"""
        short_queries = ["hi", "ok", "no", ""]
        
        for query in short_queries:
            lang = real_youtube_platform._detect_query_language(query)
            assert lang == 'en', f"Short query '{query}' should default to English"
    
    def test_url_detection_bypass(self, real_youtube_platform):
        """Test that URLs bypass language detection"""
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ"
        ]
        
        for url in urls:
            lang = real_youtube_platform._detect_query_language(url)
            assert lang == 'en', f"URL '{url}' should default to English"


@pytest.mark.integration 
class TestLanguageAPIIntegration:
    """Test integration of language detection with API parameters"""
    
    def test_language_to_api_params_mapping(self, real_youtube_platform):
        """Test that all supported languages map to correct API parameters"""
        test_cases = [
            ('en', {'regionCode': 'US', 'relevanceLanguage': 'en', 'hl': 'en'}),
            ('es', {'regionCode': 'ES', 'relevanceLanguage': 'es', 'hl': 'es'}),
            ('fr', {'regionCode': 'FR', 'relevanceLanguage': 'fr', 'hl': 'fr'}),
            ('de', {'regionCode': 'DE', 'relevanceLanguage': 'de', 'hl': 'de'}),
            ('ja', {'regionCode': 'JP', 'relevanceLanguage': 'ja', 'hl': 'ja'}),
            ('ko', {'regionCode': 'KR', 'relevanceLanguage': 'ko', 'hl': 'ko'}),
            ('zh', {'regionCode': 'CN', 'relevanceLanguage': 'zh', 'hl': 'zh'}),
            ('pt', {'regionCode': 'BR', 'relevanceLanguage': 'pt', 'hl': 'pt'}),
        ]
        
        for lang_code, expected_params in test_cases:
            params = real_youtube_platform._get_api_parameters_for_language(lang_code)
            assert params == expected_params, f"Language {lang_code} should map to {expected_params}"
    
    def test_unsupported_language_fallback(self, real_youtube_platform):
        """Test that unsupported languages fall back to English"""
        unsupported_langs = ['xyz', 'unknown', 'invalid']
        
        for lang in unsupported_langs:
            params = real_youtube_platform._get_api_parameters_for_language(lang)
            expected = {'regionCode': 'US', 'relevanceLanguage': 'en', 'hl': 'en'}
            assert params == expected, f"Unsupported language {lang} should fall back to English"


@pytest.mark.integration
class TestFullWorkflow:
    """Test the full language-aware search workflow"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_language_detection(self, real_youtube_platform):
        """Test end-to-end language detection and API parameter setting"""
        test_queries = [
            ("popular music", "en", "US"),
            ("música popular", "es", "ES"), 
            ("musique populaire", "fr", "FR"),
            ("deutsche musik", "de", "DE"),
        ]
        
        for query, expected_lang, expected_region in test_queries:
            # Test language detection
            detected_lang = real_youtube_platform._detect_query_language(query)
            assert detected_lang == expected_lang, f"Query '{query}' should detect as {expected_lang}"
            
            # Test API parameter generation
            params = real_youtube_platform._get_api_parameters_for_language(detected_lang)
            assert params['regionCode'] == expected_region, f"Language {detected_lang} should use region {expected_region}"
            assert params['relevanceLanguage'] == expected_lang, f"Should set relevanceLanguage to {expected_lang}"
            assert params['hl'] == expected_lang, f"Should set hl to {expected_lang}"


def test_manual_language_detection():
    """Manual test for language detection - can be run independently"""
    try:
        from langdetect import detect
        DetectorFactory.seed = 0
        
        test_phrases = [
            "popular music videos",      # English
            "música popular española",   # Spanish
            "musique française moderne", # French  
            "deutsche klassische musik", # German
            "日本の人気音楽",             # Japanese
            "música brasileira sertaneja", # Portuguese
        ]
        
        for phrase in test_phrases:
            try:
                detected = detect(phrase)
                print(f"'{phrase}' -> {detected}")
            except Exception as e:
                print(f"'{phrase}' -> ERROR: {e}")
                
    except ImportError:
        print("langdetect not installed - install with: pip install langdetect")


if __name__ == "__main__":
    # Run manual test
    test_manual_language_detection()
    
    # Run pytest
    pytest.main([__file__, "-v", "-m", "integration"])