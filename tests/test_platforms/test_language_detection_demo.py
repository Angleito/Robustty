#!/usr/bin/env python3
"""
Demo script for YouTube language preference functionality.

This script demonstrates the language detection and API parameter generation
that would be used in the actual YouTube platform implementation.

Run with: python test_language_detection_demo.py
"""

import sys
from typing import Dict, Any

# Simple mock language detector for demo
class SimpleLanguageDetector:
    """Simple language detector based on keyword patterns"""
    
    # Language keywords for detection
    LANGUAGE_KEYWORDS = {
        'en': ['popular', 'music', 'song', 'video', 'best', 'top', 'latest', 'new'],
        'es': ['música', 'canción', 'popular', 'español', 'latino', 'reggaeton'],
        'fr': ['musique', 'chanson', 'français', 'populaire', 'classique'],
        'de': ['musik', 'lied', 'deutsch', 'klassisch', 'populär', 'neue'],
        'ja': ['音楽', 'ミュージック', '人気', '日本', 'ポップ', 'ロック'],
        'pt': ['música', 'canção', 'brasileiro', 'sertanejo', 'popular'],
        'it': ['musica', 'canzone', 'italiano', 'popolare', 'classica'],
        'ko': ['음악', '노래', '인기', '한국', '케이팝', '트로트'],
    }
    
    @classmethod
    def detect_language(cls, text: str) -> str:
        """Detect language based on keyword presence"""
        text_lower = text.lower()
        
        # Score each language based on keyword matches
        scores = {}
        for lang, keywords in cls.LANGUAGE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[lang] = score
        
        if not scores:
            return 'en'  # Default to English
        
        # Return language with highest score
        return max(scores, key=scores.get)


class LanguageAwareSearchDemo:
    """Demo class showing language-aware search functionality"""
    
    def __init__(self):
        self.detector = SimpleLanguageDetector()
        self.enable_language_detection = True
        self.default_language = 'en'
    
    def detect_query_language(self, query: str) -> str:
        """Detect the language of a search query"""
        if not self.enable_language_detection:
            return self.default_language
        
        # Skip language detection for URLs
        if self._is_url(query):
            return self.default_language
        
        # Skip for very short queries
        if len(query.strip()) < 3:
            return self.default_language
        
        try:
            return self.detector.detect_language(query)
        except Exception:
            return self.default_language
    
    def _is_url(self, text: str) -> bool:
        """Simple URL detection"""
        return any(text.startswith(prefix) for prefix in ['http://', 'https://', 'www.'])
    
    def get_api_parameters(self, language: str) -> Dict[str, str]:
        """Get YouTube API parameters for a given language"""
        language_config = {
            'en': {'regionCode': 'US', 'relevanceLanguage': 'en', 'hl': 'en'},
            'es': {'regionCode': 'ES', 'relevanceLanguage': 'es', 'hl': 'es'},
            'fr': {'regionCode': 'FR', 'relevanceLanguage': 'fr', 'hl': 'fr'},
            'de': {'regionCode': 'DE', 'relevanceLanguage': 'de', 'hl': 'de'},
            'ja': {'regionCode': 'JP', 'relevanceLanguage': 'ja', 'hl': 'ja'},
            'pt': {'regionCode': 'BR', 'relevanceLanguage': 'pt', 'hl': 'pt'},
            'it': {'regionCode': 'IT', 'relevanceLanguage': 'it', 'hl': 'it'},
            'ko': {'regionCode': 'KR', 'relevanceLanguage': 'ko', 'hl': 'ko'},
        }
        
        return language_config.get(language, language_config['en'])
    
    def get_ytdlp_headers(self, language: str) -> Dict[str, str]:
        """Get yt-dlp headers for language preferences"""
        if language == 'en':
            return {}
        
        language_headers = {
            'es': 'es-ES,es;q=0.9,en;q=0.8',
            'fr': 'fr-FR,fr;q=0.9,en;q=0.8',
            'de': 'de-DE,de;q=0.9,en;q=0.8',
            'ja': 'ja-JP,ja;q=0.9,en;q=0.8',
            'pt': 'pt-BR,pt;q=0.9,en;q=0.8',
            'it': 'it-IT,it;q=0.9,en;q=0.8',
            'ko': 'ko-KR,ko;q=0.9,en;q=0.8',
        }
        
        accept_lang = language_headers.get(language)
        return {'Accept-Language': accept_lang} if accept_lang else {}
    
    def process_search_query(self, query: str) -> Dict[str, Any]:
        """Process a search query and return language-aware configuration"""
        # Detect language
        detected_language = self.detect_query_language(query)
        
        # Get API parameters
        api_params = self.get_api_parameters(detected_language)
        
        # Get yt-dlp headers
        ytdlp_headers = self.get_ytdlp_headers(detected_language)
        
        return {
            'query': query,
            'detected_language': detected_language,
            'api_parameters': api_params,
            'ytdlp_headers': ytdlp_headers,
            'language_detection_used': detected_language != self.default_language
        }


def main():
    """Demo script main function"""
    print("🎵 YouTube Language Preference Demo")
    print("=" * 50)
    
    demo = LanguageAwareSearchDemo()
    
    # Test queries in different languages
    test_queries = [
        # English queries
        "popular music 2024",
        "best rock songs",
        "latest pop hits",
        
        # Spanish queries  
        "música popular española",
        "reggaeton nuevo 2024",
        "canciones románticas",
        
        # French queries
        "musique française classique",
        "chansons populaires",
        "musique moderne",
        
        # German queries
        "deutsche musik klassisch",
        "neue deutsche lieder",
        "populär musik",
        
        # Japanese queries
        "日本の人気音楽",
        "ポップミュージック",
        
        # Portuguese queries
        "música brasileira sertanejo",
        "canções populares",
        
        # URLs (should not be language detected)
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        
        # Mixed/edge cases
        "música popular english song",
        "2024 music hits",
        "",  # Empty query
        "hi",  # Very short query
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        result = demo.process_search_query(query)
        
        print(f"   🌍 Language: {result['detected_language']}")
        print(f"   🔧 Language Detection Used: {result['language_detection_used']}")
        
        # Show API parameters
        api_params = result['api_parameters']
        print(f"   📡 API Params:")
        print(f"      regionCode: {api_params['regionCode']}")
        print(f"      relevanceLanguage: {api_params['relevanceLanguage']}")
        print(f"      hl: {api_params['hl']}")
        
        # Show yt-dlp headers if any
        headers = result['ytdlp_headers']
        if headers:
            print(f"   🔗 yt-dlp Headers:")
            for key, value in headers.items():
                print(f"      {key}: {value}")
        else:
            print(f"   🔗 yt-dlp Headers: None (using default)")
    
    print("\n" + "=" * 50)
    print("✅ Demo completed!")
    print("\nKey Benefits:")
    print("• English queries → US region, English results")
    print("• Non-English queries → Appropriate region & language")  
    print("• URLs always use default settings (no language bias)")
    print("• yt-dlp fallback respects same language preferences")
    print("• Graceful fallback to English for detection errors")


if __name__ == "__main__":
    main()