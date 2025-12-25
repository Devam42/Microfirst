"""
Voice Manager - Coordinates STT and TTS
Main interface for voice input/output in Microbot
"""

from typing import Optional, Tuple
from .tts_manager import TTSManager
from .stt_manager import STTManager


class VoiceManager:
    """Manages voice input (STT) and output (TTS)"""
    
    def __init__(self, aws_region: str = "ap-south-1",
                 aws_access_key: Optional[str] = None,
                 aws_secret_key: Optional[str] = None,
                 config_store = None,
                 use_advanced_audio: bool = False):
        """
        Initialize Voice Manager with PHASE 1 ML-grade audio processing
        
        Args:
            aws_region: AWS region for Polly
            aws_access_key: AWS access key (or use env variable)
            aws_secret_key: AWS secret key (or use env variable)
            config_store: ConfigStore instance for persisting voice settings
            use_advanced_audio: Enable PHASE 1 advanced audio processing
        """
        self.tts = None
        self.stt = None
        self.config = config_store
        self.use_advanced_audio = use_advanced_audio
        
        # Try to initialize TTS (AWS Polly)
        try:
            self.tts = TTSManager(
                aws_region=aws_region,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key
            )
            print("✅ TTS (Text-to-Speech) ready")
        except Exception as e:
            print(f"⚠️ TTS initialization failed: {e}")
            print("   Voice output will be disabled. Set AWS credentials to enable.")
            self.tts = None
        
        # Try to initialize STT (Speech Recognition) with PHASE 1 upgrade
        try:
            self.stt = STTManager(use_advanced=use_advanced_audio)
            
            if self.stt.is_using_advanced():
                print("✅ STT (Speech-to-Text) ready with PHASE 1 ML processing")
            else:
                print("✅ STT (Speech-to-Text) ready (standard mode)")
        except Exception as e:
            print(f"⚠️ STT initialization failed: {e}")
            print("   Voice input will be disabled.")
            self.stt = None
        
        # Voice mode state
        self.voice_mode_active = False
        self.current_language = "english"
        
        # Restore current voice from config if available
        if self.config and self.tts:
            saved_voice = self.config.get_current_voice()
            self.tts.set_voice(saved_voice)
    
    def activate_voice_mode(self, language: str = "english") -> Tuple[bool, str]:
        """
        Activate voice mode (both STT and TTS)
        
        Args:
            language: Current language setting
        
        Returns:
            Tuple of (success, message)
        """
        if not self.tts and not self.stt:
            return False, "❌ Voice system not available. Please configure AWS credentials."
        
        self.voice_mode_active = True
        self.current_language = language
        
        # Set appropriate voice based on language
        if self.tts:
            voice = self.tts.get_voice_for_language(language)
            self.tts.set_voice(voice)
        
        message = "🎙️ Voice Mode Activated!\n\n"
        
        if self.tts:
            voice_info = self.tts.VOICES[self.tts.current_voice]
            message += f"🔊 Voice Output: {voice_info['voice_id']} ({voice_info['description']})\n"
        else:
            message += "🔇 Voice Output: Not available\n"
        
        if self.stt:
            message += "🎤 Voice Input: Ready\n"
        else:
            message += "🎤 Voice Input: Not available\n"
        
        message += f"🌍 Language: {language.title()}\n"
        message += "\n💡 Speak your message when you see 🎤 Listening...\n"
        message += "💡 Type 'exit voice mode' to return to text chat"
        
        return True, message
    
    def deactivate_voice_mode(self) -> str:
        """
        Deactivate voice mode
        
        Returns:
            Confirmation message
        """
        self.voice_mode_active = False
        return "✅ Voice mode deactivated. Back to text chat."
    
    def listen_for_input(self, timeout: int = 20) -> Tuple[bool, str]:
        """
        Listen for voice input - natural conversation timing
        
        Args:
            timeout: Seconds to wait for speech (default 20s like a patient human)
        
        Returns:
            Tuple of (success, text or error_message)
        """
        if not self.voice_mode_active:
            return False, "Voice mode not active"
        
        if not self.stt:
            return False, "Speech recognition not available"
        
        # Get language code for recognition
        lang_code = self.stt.get_language_code(self.current_language)
        
        # Listen with natural timeout
        return self.stt.listen(timeout=timeout, language=lang_code)
    
    def speak_response(self, text: str, emotion: str = "neutral") -> bool:
        """
        Speak response using TTS
        
        Args:
            text: Text to speak
            emotion: Emotion for speech (neutral, happy, sad, etc.)
        
        Returns:
            True if spoken successfully
        """
        if not self.voice_mode_active:
            return False
        
        if not self.tts:
            return False
        
        # Get emotion parameters
        params = self._get_emotion_parameters(emotion)
        
        # Speak
        return self.tts.speak(text, **params)
    
    def set_voice(self, voice_name: str) -> Tuple[bool, str]:
        """
        Change TTS voice
        
        Args:
            voice_name: Voice name (matthew, justin, salli, aditi)
        
        Returns:
            Tuple of (success, message)
        """
        if not self.tts:
            return False, "❌ TTS not available"
        
        voice_name = voice_name.lower()
        
        if voice_name not in self.tts.VOICES:
            available = ", ".join(self.tts.VOICES.keys())
            return False, f"❌ Unknown voice. Available: {available}"
        
        success = self.tts.set_voice(voice_name)
        
        if success:
            # Save current voice to config
            if self.config:
                self.config.set_current_voice(voice_name)
            
            voice_info = self.tts.VOICES[voice_name]
            return True, f"✅ Voice changed to {voice_info['voice_id']} ({voice_info['description']})"
        else:
            return False, "❌ Failed to change voice"
    
    def get_available_voices(self) -> dict:
        """Get all available voices"""
        if self.tts:
            return self.tts.get_available_voices()
        return {}
    
    def update_language(self, language: str):
        """
        Update language setting and auto-switch voice
        
        Args:
            language: New language (english, hinglish, marathi)
        """
        self.current_language = language
        
        if self.tts and self.voice_mode_active:
            # Auto-switch voice based on language
            voice = self.tts.get_voice_for_language(language)
            self.tts.set_voice(voice)
            print(f"🌍 Language changed to {language}, voice auto-switched to {voice}")
    
    def _get_emotion_parameters(self, emotion: str) -> dict:
        """
        Get prosody parameters for emotion
        
        Args:
            emotion: Emotion name
        
        Returns:
            Dict with pitch, rate, volume parameters
        """
        emotion_map = {
            "neutral": {"pitch": "+0%", "rate": "100%", "volume": "medium"},
            "happy": {"pitch": "+5%", "rate": "110%", "volume": "loud"},
            "cheerful": {"pitch": "+5%", "rate": "110%", "volume": "loud"},
            "excited": {"pitch": "+10%", "rate": "115%", "volume": "x-loud"},
            "sad": {"pitch": "-5%", "rate": "85%", "volume": "soft"},
            "disappointed": {"pitch": "-5%", "rate": "85%", "volume": "soft"},
            "angry": {"pitch": "-8%", "rate": "100%", "volume": "x-loud"},
            "frustrated": {"pitch": "-8%", "rate": "100%", "volume": "x-loud"},
            "friendly": {"pitch": "+3%", "rate": "105%", "volume": "medium"},
            "warm": {"pitch": "+3%", "rate": "105%", "volume": "medium"},
        }
        
        return emotion_map.get(emotion.lower(), emotion_map["neutral"])
    
    def is_voice_mode_active(self) -> bool:
        """Check if voice mode is active"""
        return self.voice_mode_active
    
    def is_available(self) -> bool:
        """Check if voice system is available"""
        return self.tts is not None or self.stt is not None
    
    def get_status(self) -> dict:
        """Get voice system status with PHASE 1 statistics"""
        status = {
            "voice_mode_active": self.voice_mode_active,
            "tts_available": self.tts is not None,
            "stt_available": self.stt is not None,
            "current_language": self.current_language,
            "current_voice": self.tts.current_voice if self.tts else None,
            "advanced_audio_enabled": self.use_advanced_audio
        }
        
        # Add PHASE 1 statistics if available
        if self.stt and self.stt.is_using_advanced():
            status["stt_statistics"] = self.stt.get_statistics()
        
        return status
    
    def get_audio_statistics(self) -> dict:
        """Get PHASE 1 audio processing statistics"""
        if self.stt:
            return self.stt.get_statistics()
        return {"error": "STT not available"}
    
    def reset_audio_statistics(self):
        """Reset PHASE 1 audio processing statistics"""
        if self.stt:
            self.stt.reset_statistics()

