"""
Speech-to-Text Manager
PHASE 1 UPGRADE: Advanced audio processing with RNNoise, VAD, and Whisper
"""

import speech_recognition as sr
import numpy as np
from typing import Optional, Tuple
import threading
import queue

try:
    from .advanced_audio_processor import AdvancedAudioProcessor
    ADVANCED_PROCESSOR_AVAILABLE = True
except ImportError:
    ADVANCED_PROCESSOR_AVAILABLE = False
    print("⚠️ Advanced audio processor not available - using fallback")


class STTManager:
    """
    Speech-to-Text Manager with ML-grade audio processing
    
    Phase 1 Features:
    - RNNoise neural noise suppression
    - Silero VAD (voice activity detection)
    - Whisper ASR (better than Google SR)
    - Confidence filtering
    """
    
    def __init__(self, use_advanced: bool = True):
        """
        Initialize speech recognition
        
        Args:
            use_advanced: Use advanced ML processing (Phase 1)
        """
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.enabled = True
        
        # PHASE 1: Advanced audio processor
        self.use_advanced = use_advanced and ADVANCED_PROCESSOR_AVAILABLE
        self.advanced_processor = None
        
        if self.use_advanced:
            try:
                print("🚀 Initializing PHASE 1 Advanced Audio Processing...")
                self.advanced_processor = AdvancedAudioProcessor(
                    sampling_rate=16000,
                    confidence_threshold=0.6  # Minimum 60% confidence
                )
                
                if self.advanced_processor.is_available():
                    print("✅ STT Manager initialized with PHASE 1 ML processing")
                    print("   🎯 Features: RNNoise + VAD + Enhanced Google SR + Confidence")
                    self._print_capabilities()
                else:
                    print("⚠️ Some advanced features unavailable - using partial upgrade")
                    self.use_advanced = False
            except Exception as e:
                print(f"⚠️ Advanced processor init failed: {e}")
                self.use_advanced = False
                self.advanced_processor = None
        
        # Fallback: Standard Google SR settings (if advanced not available)
        if not self.use_advanced:
            print("✅ STT Manager initialized with standard Google SR")
            self._setup_standard_recognizer()
        
        # Adjust for ambient noise on first use
        self._calibrated = False
    
    def _setup_standard_recognizer(self):
        """Setup standard Google SR with balanced settings for ACCURACY + SPEED"""
        self.recognizer.energy_threshold = 2500
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.10
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 1.2  # Balanced: wait for natural pauses (increased from 0.8)
        self.recognizer.phrase_threshold = 0.2
        self.recognizer.non_speaking_duration = 1.2  # Balanced: don't cut off mid-sentence (increased from 0.8)
    
    def _print_capabilities(self):
        """Print available capabilities"""
        if self.advanced_processor:
            caps = self.advanced_processor.get_capabilities()
            print("   📊 Capabilities:")
            print(f"      • Noise Suppression: {'✅' if caps['noise_suppression'] else '❌'}")
            print(f"      • Voice Detection: {'✅' if caps['vad'] else '❌'}")
            print(f"      • Enhanced Google SR: {'✅' if caps['enhanced_google_asr'] else '❌'}")
            print(f"      • Confidence Filter: {'✅' if caps['confidence_filtering'] else '❌'}")
    
    def _ensure_microphone(self) -> bool:
        """Ensure microphone is available"""
        if self.microphone is None:
            try:
                self.microphone = sr.Microphone()
                print("🎤 Microphone ready")
                return True
            except Exception as e:
                # Only print error once, not repeatedly
                if not hasattr(self, '_mic_error_shown'):
                    print(f"⚠️ No microphone detected - API mode only")
                    self._mic_error_shown = True
                return False
        return True
    
    def _calibrate_noise(self):
        """Calibrate for ambient noise (one-time on first use) - FAST"""
        if self._calibrated or not self._ensure_microphone():
            return
        
        try:
            with self.microphone as source:
                # Quick calibration - 0.3 seconds for better accuracy
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                # Lower threshold for faster detection (but not too low to avoid noise)
                self.recognizer.energy_threshold = max(self.recognizer.energy_threshold, 2500)
                # Enable dynamic energy threshold for auto-adjustment
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.dynamic_energy_adjustment_damping = 0.15
                self.recognizer.dynamic_energy_ratio = 1.5
            self._calibrated = True
            print(f"Microphone ready (threshold: {self.recognizer.energy_threshold:.0f})")
        except Exception as e:
            print(f"Calibration warning: {e}")
    
    def listen(self, timeout: int = 20, phrase_time_limit: Optional[int] = None,
               language: str = "en-US") -> Tuple[bool, str]:
        """
        Listen for speech input with PHASE 1 ML-grade processing
        
        Pipeline (if advanced):
        1. Capture audio from microphone
        2. RNNoise neural noise suppression
        3. Silero VAD (voice activity detection)
        4. Enhanced Google SR transcription
        5. Confidence filtering (>60%)
        
        Args:
            timeout: Seconds to wait for speech to start
            phrase_time_limit: Max seconds for phrase
            language: Language code (en-US, hi-IN, etc.)
        
        Returns:
            Tuple of (success, text or error_message)
        """
        if not self.enabled:
            return False, "STT is disabled"
        
        if not self._ensure_microphone():
            return False, "Microphone not available"
        
        # Calibrate on first use
        self._calibrate_noise()
        
        try:
            # Capture audio from microphone
            with self.microphone as source:
                # NO ambient adjustment during listen - already calibrated!
                # This saves 0.2 seconds per request
                
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit or 6  # Balanced: complete messages but faster
                )
            
            # PHASE 1: Use advanced ML processing if available
            if self.use_advanced and self.advanced_processor:
                return self._process_with_advanced(audio, language)
            else:
                # Fallback: Standard Google SR
                return self._process_with_google_sr(audio, language)
        
        except sr.WaitTimeoutError:
            return False, "TIMEOUT"  # Silent - just return code
        
        except sr.RequestError as e:
            return False, f"API_ERROR"  # Silent - just return code
        
        except Exception as e:
            return False, f"STT_ERROR"  # Silent - just return code
    
    def _process_with_advanced(self, audio: sr.AudioData, language: str) -> Tuple[bool, str]:
        """
        Process audio with PHASE 1 advanced ML pipeline
        
        Args:
            audio: Captured audio data
            language: Language code
        
        Returns:
            (success, text or error)
        """
        try:
            print("🚀 Processing with PHASE 1 ML pipeline...")
            
            # Convert audio to numpy array (16kHz, mono)
            audio_np = np.frombuffer(audio.get_raw_data(), dtype=np.int16).astype(np.float32)
            audio_np = audio_np / 32768.0  # Normalize to [-1, 1]
            
            # Convert language code to simple format for Whisper
            lang_code = "en" if "en" in language else "hi"
            
            # Process through advanced pipeline
            # Pipeline: RNNoise → VAD → Enhanced Google SR → Confidence Filter
            text, metadata = self.advanced_processor.process_audio(
                audio_np,
                language=lang_code,
                skip_vad=False  # Use VAD to filter noise
            )
            
            # Check results
            if text and len(text.strip()) > 0:
                confidence = metadata.get("confidence", 0.0)
                speech_prob = metadata.get("speech_probability", 0.0)
                
                print(f"✅ You said: \"{text}\"")
                print(f"   📊 Confidence: {confidence:.1%} | Speech: {speech_prob:.1%}")
                
                # Show processing stages
                stages = metadata.get("processing_stages", [])
                if stages:
                    print(f"   🔧 Pipeline: {' → '.join(stages)}")
                
                return True, text.strip()
            
            elif not metadata.get("vad_detected", False):
                # VAD filtered out - no speech detected
                print("   ℹ️ VAD: No speech detected (background noise)")
                return False, "❓ No speech detected - only background noise"
            
            elif metadata.get("confidence", 0) < 0.6:
                # Low confidence transcription
                print(f"   ⚠️ Low confidence: {metadata.get('confidence', 0):.1%}")
                return False, "❓ Speech unclear - please speak more clearly"
            
            else:
                return False, "❓ Could not transcribe - please try again"
        
        except Exception as e:
            print(f"⚠️ Advanced processing failed: {e}")
            # Fallback to Google SR
            print("   🔄 Falling back to Google SR...")
            return self._process_with_google_sr(audio, language)
    
    def _process_with_google_sr(self, audio: sr.AudioData, language: str) -> Tuple[bool, str]:
        """
        Process audio with standard Google Speech Recognition (fallback)
        
        Args:
            audio: Captured audio data
            language: Language code
        
        Returns:
            (success, text or error)
        """
        try:
            # ULTRA FAST: Direct recognition with optimized settings
            text = self.recognizer.recognize_google(
                audio, 
                language=language, 
                show_all=False
            )
            
            if text and len(text.strip()) > 0:
                print(f"You said: \"{text}\"")
                return True, text.strip()
            else:
                return False, "No speech"
        
        except sr.UnknownValueError:
            return False, "Unclear"
        except Exception as e:
            return False, "Error"
    
    def listen_in_background(self, callback, language: str = "en-US"):
        """
        Listen continuously in background (advanced feature)
        
        Args:
            callback: Function to call with recognized text
            language: Language code
        
        Returns:
            Stop function to stop listening
        """
        if not self.enabled or not self._ensure_microphone():
            return None
        
        # Calibrate first
        self._calibrate_noise()
        
        def recognize_callback(recognizer, audio):
            try:
                text = recognizer.recognize_google(audio, language=language)
                callback(text)
            except sr.UnknownValueError:
                pass  # Ignore unintelligible audio
            except sr.RequestError as e:
                print(f"❌ Recognition error: {e}")
        
        # Start background listening
        stop_listening = self.recognizer.listen_in_background(
            self.microphone, 
            recognize_callback
        )
        
        print("🎤 Background listening started")
        return stop_listening
    
    def get_language_code(self, language: str) -> str:
        """
        Convert language name to speech recognition language code
        
        Args:
            language: Language name (english, hinglish, marathi)
        
        Returns:
            Language code for speech recognition
        """
        language_lower = language.lower()
        
        # Use appropriate language code for better recognition
        if language_lower in ["hinglish", "hindi"]:
            # Use hi-IN for Hindi/Hinglish - better recognition for Indian accent
            return "hi-IN"
        elif language_lower == "marathi":
            return "mr-IN"
        elif language_lower in ["english", "en"]:
            # For English mode, use en-US which has better general recognition
            # en-IN has issues with Indian English accents sometimes
            return "en-US"
        else:
            # Default to en-IN for other cases
            return "en-IN"
    
    def enable(self):
        """Enable STT"""
        self.enabled = True
        print("🎤 STT enabled")
    
    def disable(self):
        """Disable STT"""
        self.enabled = False
        print("🔇 STT disabled")
    
    def is_enabled(self) -> bool:
        """Check if STT is enabled"""
        return self.enabled
    
    def test_microphone(self) -> bool:
        """
        Test if microphone is working
        
        Returns:
            True if microphone works, False otherwise
        """
        if not self._ensure_microphone():
            return False
        
        try:
            with self.microphone as source:
                print("🎤 Testing microphone... Say something!")
                audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=6)  # Fast but complete
                text = self.recognizer.recognize_google(audio)
                print(f"✅ Microphone works! Heard: \"{text}\"")
                return True
        except Exception as e:
            print(f"❌ Microphone test failed: {e}")
            return False
    
    def get_statistics(self) -> dict:
        """
        Get PHASE 1 processing statistics
        
        Returns:
            Statistics dict (if advanced processor available)
        """
        if self.use_advanced and self.advanced_processor:
            stats = self.advanced_processor.get_statistics()
            return {
                "mode": "advanced_ml",
                "features": ["RNNoise", "Silero VAD", "Enhanced Google SR", "Confidence Filter"],
                **stats
            }
        else:
            return {
                "mode": "standard_google_sr",
                "features": ["Google Speech Recognition"]
            }
    
    def reset_statistics(self):
        """Reset processing statistics"""
        if self.use_advanced and self.advanced_processor:
            self.advanced_processor.reset_statistics()
    
    def is_using_advanced(self) -> bool:
        """Check if using advanced ML processing"""
        return self.use_advanced and self.advanced_processor is not None

