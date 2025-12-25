"""
Text-to-Speech Manager using AWS Polly
Supports multiple voices: Matthew, Justin, Salli (English), Aditi (Hinglish)
"""

import boto3
from contextlib import closing
import io
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from typing import Optional, Dict, Any
import os


class TTSManager:
    """AWS Polly Text-to-Speech Manager"""
    
    # Voice configurations
    VOICES = {
        "matthew": {
            "voice_id": "Matthew",
            "language": "en-US",
            "gender": "Male",
            "engine": "neural",  # Neural engine is faster and sounds better
            "description": "US Male - Clear and professional"
        },
        "justin": {
            "voice_id": "Justin",
            "language": "en-US", 
            "gender": "Male",
            "engine": "standard",  # Justin only available in standard
            "description": "US Male Child - Young and energetic"
        },
        "salli": {
            "voice_id": "Salli",
            "language": "en-US",
            "gender": "Female",
            "engine": "neural",  # Neural engine is faster and sounds better
            "description": "US Female - Friendly and warm"
        },
        "aditi": {
            "voice_id": "Aditi",
            "language": "hi-IN",
            "gender": "Female",
            "engine": "standard",  # Aditi only available in standard
            "description": "Indian Female - Perfect for Hinglish"
        }
    }
    
    def __init__(self, aws_region: str = "ap-south-1", 
                 aws_access_key: Optional[str] = None,
                 aws_secret_key: Optional[str] = None):
        """
        Initialize AWS Polly TTS
        
        Args:
            aws_region: AWS region (default: ap-south-1 for India)
            aws_access_key: AWS access key (or use env MICROBOT_AWS_ACCESS_KEY or AWS_ACCESS_KEY_ID)
            aws_secret_key: AWS secret key (or use env MICROBOT_AWS_SECRET_KEY or AWS_SECRET_ACCESS_KEY)
        """
        # Get credentials from parameters or environment variables
        # Try multiple env var names for compatibility
        self.aws_access_key = (
            aws_access_key or 
            os.getenv("MICROBOT_AWS_ACCESS_KEY") or 
            os.getenv("AWS_ACCESS_KEY_ID")
        )
        self.aws_secret_key = (
            aws_secret_key or 
            os.getenv("MICROBOT_AWS_SECRET_KEY") or 
            os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        
        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError(
                "AWS credentials not provided. Please set one of the following:\n"
                "  - MICROBOT_AWS_ACCESS_KEY and MICROBOT_AWS_SECRET_KEY environment variables\n"
                "  - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                "  - Pass credentials directly to the constructor\n"
                "See .env.example for setup instructions."
            )
        
        try:
            self.polly = boto3.client(
                'polly',
                region_name=aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key
            )
            print("✅ AWS Polly TTS initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize AWS Polly: {e}")
            raise
        
        self.current_voice = "justin"  # Default voice (young, energetic)
        self.enabled = True
    
    def set_voice(self, voice_name: str) -> bool:
        """
        Set the current voice
        
        Args:
            voice_name: Voice name (matthew, justin, salli, aditi)
        
        Returns:
            True if voice set successfully, False otherwise
        """
        voice_name = voice_name.lower()
        if voice_name in self.VOICES:
            self.current_voice = voice_name
            print(f"🎙️ Voice changed to: {self.VOICES[voice_name]['voice_id']} ({self.VOICES[voice_name]['description']})")
            return True
        else:
            print(f"❌ Unknown voice: {voice_name}")
            return False
    
    def get_voice_for_language(self, language: str) -> str:
        """
        Get appropriate voice based on language
        
        Args:
            language: Language code (english, hinglish, marathi)
        
        Returns:
            Voice name
        """
        if language.lower() in ["hinglish", "marathi", "hindi"]:
            return "aditi"
        else:
            return self.current_voice if self.current_voice != "aditi" else "justin"
    
    def synthesize(self, text: str, voice_name: Optional[str] = None,
                   pitch: str = "+0%", rate: str = "125%", volume: str = "medium") -> Optional[bytes]:
        """
        Synthesize speech from text
        
        Args:
            text: Text to convert to speech
            voice_name: Override voice (optional)
            pitch: Pitch adjustment (-20% to +20%)
            rate: Speaking rate (80% to 120%)
            volume: Volume level (soft, medium, loud, x-loud)
        
        Returns:
            Audio data (MP3 bytes) or None on error
        """
        if not self.enabled:
            return None
        
        # Use specified voice or current voice
        voice = voice_name or self.current_voice
        
        if voice not in self.VOICES:
            print(f"⚠️ Invalid voice '{voice}', using default")
            voice = self.current_voice
        
        voice_config = self.VOICES[voice]
        
        # Build SSML with prosody control
        ssml = '<speak>'
        ssml += f'<prosody pitch="{pitch}" rate="{rate}" volume="{volume}">'
        ssml += self._escape_ssml(text)
        ssml += '</prosody>'
        ssml += '</speak>'
        
        try:
            response = self.polly.synthesize_speech(
                Text=ssml,
                TextType='ssml',
                OutputFormat='mp3',
                VoiceId=voice_config['voice_id'],
                Engine=voice_config['engine']
            )
            
            if "AudioStream" in response:
                with closing(response["AudioStream"]) as stream:
                    return stream.read()
        
        except Exception as e:
            print(f"❌ TTS Error: {e}")
            return None
        
        return None
    
    def play_audio(self, audio_data: bytes) -> bool:
        """
        Play audio through speakers
        
        Args:
            audio_data: MP3 audio bytes
        
        Returns:
            True if played successfully, False otherwise
        """
        if not audio_data:
            return False
        
        try:
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            
            # ULTRA FAST: No silence added for instant response
            # silence = AudioSegment.silent(duration=100)
            # audio = audio + silence
            
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Handle stereo
            if audio.channels == 2:
                samples = samples.reshape((-1, 2))
            
            # Normalize
            samples = samples / (2**15)
            
            # Play
            sd.play(samples, audio.frame_rate)
            sd.wait()  # Wait for playback to complete
            
            # No extra sleep needed - removed 0.2s delay for faster response
            
            return True
        
        except Exception as e:
            print(f"❌ Audio playback error: {e}")
            return False
    
    def speak(self, text: str, voice_name: Optional[str] = None, **kwargs) -> bool:
        """
        Synthesize and play speech
        
        Args:
            text: Text to speak
            voice_name: Override voice (optional)
            **kwargs: Additional parameters (pitch, rate, volume)
        
        Returns:
            True if spoken successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        audio_data = self.synthesize(text, voice_name, **kwargs)
        if audio_data:
            return self.play_audio(audio_data)
        
        return False
    
    def _escape_ssml(self, text: str) -> str:
        """Escape special characters for SSML"""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&apos;")
        return text
    
    def calculate_cost(self, text: str) -> float:
        """
        Calculate cost in INR (Standard engine)
        
        Args:
            text: Text to calculate cost for
        
        Returns:
            Cost in INR
        """
        chars = len(text)
        cost_usd = (chars / 1_000_000) * 4  # Standard = $4 per 1M chars
        cost_inr = cost_usd * 83  # USD to INR conversion
        return cost_inr
    
    def get_available_voices(self) -> Dict[str, Dict[str, Any]]:
        """Get all available voices with their configurations"""
        return self.VOICES.copy()
    
    def enable(self):
        """Enable TTS"""
        self.enabled = True
        print("🔊 TTS enabled")
    
    def disable(self):
        """Disable TTS"""
        self.enabled = False
        print("🔇 TTS disabled")
    
    def is_enabled(self) -> bool:
        """Check if TTS is enabled"""
        return self.enabled

