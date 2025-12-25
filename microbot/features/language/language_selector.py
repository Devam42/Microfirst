"""
Language Selector Module
Handles language selection and switching between English and Hinglish
"""

from __future__ import annotations
import re
from typing import List, Optional
from enum import Enum


class SupportedLanguage(Enum):
    """Supported languages for the chatbot"""
    ENGLISH = "english"
    HINGLISH = "hinglish"


class LanguageSelector:
    """Manages language selection and provides language-specific configurations"""
    
    def __init__(self, default_language: SupportedLanguage = SupportedLanguage.HINGLISH):
        self.current_language = default_language
        self._language_prompts = {
            SupportedLanguage.ENGLISH: {
                "select_prompt": "Please select your preferred language:\n1. English\n2. Hinglish\nEnter your choice (1 or 2): ",
                "invalid_choice": "Invalid choice. Please enter 1 for English or 2 for Hinglish.",
                "language_set": "Language set to English.",
                "language_switch": "Switched to English. I will now respond only in English.",
            },
            SupportedLanguage.HINGLISH: {
                "select_prompt": "Apni pasandida bhasha chuniye:\n1. English\n2. Hinglish\nApna choice enter kariye (1 ya 2): ",
                "invalid_choice": "Galat choice hai. English ke liye 1 ya Hinglish ke liye 2 enter kariye.",
                "language_set": "Bhasha Hinglish set kar di gayi.",
                "language_switch": "Hinglish mein switch kar diya.",
            }
        }
    
    def get_supported_languages(self) -> List[SupportedLanguage]:
        """Get list of supported languages"""
        return list(SupportedLanguage)
    
    def get_current_language(self) -> SupportedLanguage:
        """Get currently selected language"""
        return self.current_language
    
    def set_language(self, language: SupportedLanguage) -> str:
        """Set the current language and return confirmation message"""
        old_language = self.current_language
        self.current_language = language
        
        if old_language == language:
            return self._get_prompt("language_set")
        else:
            return self._get_prompt("language_switch")
    
    def set_language_by_choice(self, choice: str) -> tuple[bool, str]:
        """
        Set language by user choice (1 or 2)
        Returns (success, message)
        """
        choice = choice.strip()
        
        if choice == "1":
            message = self.set_language(SupportedLanguage.ENGLISH)
            return True, message
        elif choice == "2":
            message = self.set_language(SupportedLanguage.HINGLISH)
            return True, message
        else:
            return False, self._get_prompt("invalid_choice")
    
    def get_language_selection_prompt(self) -> str:
        """Get the language selection prompt in current language"""
        return self._get_prompt("select_prompt")
    
    def is_language_command(self, user_input: str) -> bool:
        """Check if user input is a language change command using AI"""
        try:
            # Use AI to detect language change intent
            prompt = f"""Does this user input indicate they want to CHANGE/SWITCH the conversation language between English and Hindi/Hinglish?

User input: "{user_input}"

Examples of language change commands:
- "speak in english" → YES
- "इंग्लिश में बात करो" → YES
- "switch to hindi" → YES
- "english me bolo" → YES

Examples that are NOT language change commands:
- "timer ko kitna time bacha hai" → NO (asking about timer)
- "what are you doing" → NO (regular question)
- "hello how are you" → NO (greeting)

IMPORTANT: Only respond YES if they explicitly want to change the language. Questions containing words like "english" or "hindi" but not asking to switch language should be NO.

Respond with only "YES" or "NO"."""

            # Import AI client
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "legacy_code"))
            from ...utils.genai_client import make_client
            
            client = make_client()
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            
            return response.text.strip().upper() == "YES"
        except Exception:
            # Fallback: STRICT keyword check - only explicit language switching phrases
            user_lower = user_input.lower()
            strict_keywords = [
                "में बात कर", "me baat kar", "bolo ab", "speak in", "switch to",
                "स्विच टू", "language change", "bhasha badal"
            ]
            return any(keyword in user_lower for keyword in strict_keywords)
    
    def detect_language_preference(self, user_input: str) -> Optional[SupportedLanguage]:
        """Detect language preference from user input using AI"""
        try:
            # Use AI to detect language preference
            prompt = f"""Analyze this user input and determine which language they prefer:

User input: "{user_input}"

Important context:
- "इंग्लिश" or "अंग्रेजी" means English
- "हिंदी" or "हिंग्लिश" means Hinglish
- "switch to english" or "स्विच टू इंग्लिश" means they want English

If they want English, respond with: "ENGLISH"
If they want Hinglish (Hindi-English mix), respond with: "HINGLISH"  
If unclear or no preference mentioned, respond with: "NONE"

Respond with only one of these exact words."""

            # Import AI client
            import sys
            from pathlib import Path
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "legacy_code"))
            from ...utils.genai_client import make_client
            
            client = make_client()
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            
            preference = response.text.strip().upper()
            
            if preference == "ENGLISH":
                return SupportedLanguage.ENGLISH
            elif preference == "HINGLISH":
                return SupportedLanguage.HINGLISH
            
        except Exception:
            # Fallback: simple keyword check
            user_lower = user_input.lower()
            # Check for English keywords (including Devanagari)
            english_keywords = ["english", "इंग्लिश", "अंग्रेजी", "angrezi"]
            hinglish_keywords = ["hinglish", "hindi", "हिंदी", "हिंग्लिश"]
            
            has_english = any(keyword in user_lower for keyword in english_keywords)
            has_hinglish = any(keyword in user_lower for keyword in hinglish_keywords)
            
            if has_english and not has_hinglish:
                return SupportedLanguage.ENGLISH
            elif has_hinglish:
                return SupportedLanguage.HINGLISH
        
        return None
    
    def _get_prompt(self, key: str) -> str:
        """Get prompt text for current language"""
        return self._language_prompts[self.current_language][key]
    
    def get_language_code(self) -> str:
        """Get language code as string for compatibility"""
        return self.current_language.value
    
    def is_english(self) -> bool:
        """Check if current language is English"""
        return self.current_language == SupportedLanguage.ENGLISH
    
    def is_hinglish(self) -> bool:
        """Check if current language is Hinglish"""
        return self.current_language == SupportedLanguage.HINGLISH
