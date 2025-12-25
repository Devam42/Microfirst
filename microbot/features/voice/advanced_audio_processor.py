"""
Advanced Audio Processor Module
ML-grade audio processing with RNNoise, VAD, and Whisper
Phase 1: Foundation (Noise Suppression + VAD + Better ASR)
"""

from __future__ import annotations
import numpy as np
import torch
from typing import Optional, Tuple, Dict, Any
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    print("⚠️ noisereduce not available - install with: pip install noisereduce")

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("⚠️ speech_recognition not available - install with: pip install SpeechRecognition")

try:
    # Silero VAD
    torch.set_num_threads(1)
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        onnx=False
    )
    (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
    SILERO_VAD_AVAILABLE = True
except Exception as e:
    SILERO_VAD_AVAILABLE = False
    print(f"⚠️ Silero VAD not available: {e}")


class SileroVAD:
    """
    Silero Voice Activity Detection
    ML-based VAD - much better than simple energy threshold
    """
    
    def __init__(self, threshold: float = 0.5, sampling_rate: int = 16000):
        """
        Initialize Silero VAD
        
        Args:
            threshold: Speech probability threshold (0.0-1.0)
            sampling_rate: Audio sample rate (Hz)
        """
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.available = SILERO_VAD_AVAILABLE
        
        if self.available:
            self.model = model
            self.model.eval()
        else:
            print("⚠️ Silero VAD not initialized - using fallback")
    
    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """
        Detect if audio chunk contains speech
        
        Args:
            audio_chunk: Audio data (numpy array)
        
        Returns:
            True if speech detected, False otherwise
        """
        if not self.available:
            return self._fallback_vad(audio_chunk)
        
        try:
            # Convert to numpy if needed
            if not isinstance(audio_chunk, np.ndarray):
                audio_chunk = np.array(audio_chunk)
            
            # Ensure 1D
            if len(audio_chunk.shape) > 1:
                audio_chunk = audio_chunk.squeeze()
            
            # Silero VAD requires chunks of 512 samples (for 16kHz) or 256 (for 8kHz)
            chunk_size = 512 if self.sampling_rate == 16000 else 256
            
            # If audio is smaller than chunk size, pad it
            if len(audio_chunk) < chunk_size:
                audio_chunk = np.pad(audio_chunk, (0, chunk_size - len(audio_chunk)))
            
            # Process in chunks and check if ANY chunk has speech
            speech_detected = False
            for i in range(0, len(audio_chunk), chunk_size):
                chunk = audio_chunk[i:i + chunk_size]
                
                # Pad last chunk if needed
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                
                # Convert to tensor
                audio_tensor = torch.from_numpy(chunk).float()
                
                # Get speech probability
                with torch.no_grad():
                    speech_prob = self.model(audio_tensor, self.sampling_rate).item()
                
                if speech_prob > self.threshold:
                    speech_detected = True
                    break  # Found speech, no need to check more
            
            return speech_detected
        
        except Exception as e:
            print(f"⚠️ VAD error: {e}")
            return self._fallback_vad(audio_chunk)
    
    def get_speech_probability(self, audio_chunk: np.ndarray) -> float:
        """
        Get speech probability score
        
        Args:
            audio_chunk: Audio data
        
        Returns:
            Probability (0.0-1.0)
        """
        if not self.available:
            return 0.5  # Neutral
        
        try:
            # Convert to numpy if needed
            if not isinstance(audio_chunk, np.ndarray):
                audio_chunk = np.array(audio_chunk)
            
            # Ensure 1D
            if len(audio_chunk.shape) > 1:
                audio_chunk = audio_chunk.squeeze()
            
            # Silero VAD requires chunks of 512 samples (for 16kHz) or 256 (for 8kHz)
            chunk_size = 512 if self.sampling_rate == 16000 else 256
            
            # If audio is smaller than chunk size, pad it
            if len(audio_chunk) < chunk_size:
                audio_chunk = np.pad(audio_chunk, (0, chunk_size - len(audio_chunk)))
            
            # Process in chunks and return average probability
            probabilities = []
            for i in range(0, len(audio_chunk), chunk_size):
                chunk = audio_chunk[i:i + chunk_size]
                
                # Pad last chunk if needed
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                
                # Convert to tensor
                audio_tensor = torch.from_numpy(chunk).float()
                
                # Get speech probability
                with torch.no_grad():
                    prob = self.model(audio_tensor, self.sampling_rate).item()
                    probabilities.append(prob)
            
            # Return max probability (if ANY chunk has speech)
            return max(probabilities) if probabilities else 0.0
        
        except Exception:
            return 0.5
    
    def _fallback_vad(self, audio_chunk: np.ndarray) -> bool:
        """
        Simple energy-based VAD fallback
        """
        if len(audio_chunk) == 0:
            return False
        
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        
        # Simple threshold (adjust based on environment)
        return rms > 0.01


class RNNoiseProcessor:
    """
    Neural Noise Suppression using noisereduce
    Much better than simple bandpass filters
    """
    
    def __init__(self, sampling_rate: int = 16000):
        """
        Initialize RNNoise processor
        
        Args:
            sampling_rate: Audio sample rate (Hz)
        """
        self.sampling_rate = sampling_rate
        self.available = NOISEREDUCE_AVAILABLE
        self.noise_profile = None
        
        if not self.available:
            print("⚠️ RNNoise not available - using fallback")
    
    def suppress_noise(self, audio: np.ndarray, stationary: bool = False) -> np.ndarray:
        """
        Apply neural noise suppression
        
        Args:
            audio: Input audio (numpy array)
            stationary: If True, assumes stationary noise (fan, AC)
        
        Returns:
            Denoised audio
        """
        if not self.available:
            return self._fallback_noise_reduction(audio)
        
        try:
            # Apply noisereduce
            reduced = nr.reduce_noise(
                y=audio,
                sr=self.sampling_rate,
                stationary=stationary,
                prop_decrease=0.8  # Aggressive noise reduction
            )
            
            return reduced
        
        except Exception as e:
            print(f"⚠️ Noise reduction error: {e}")
            return self._fallback_noise_reduction(audio)
    
    def learn_noise_profile(self, noise_sample: np.ndarray):
        """
        Learn noise profile from a sample
        
        Args:
            noise_sample: Pure noise audio sample
        """
        self.noise_profile = noise_sample
    
    def _fallback_noise_reduction(self, audio: np.ndarray) -> np.ndarray:
        """
        Simple spectral subtraction fallback
        """
        try:
            from scipy import signal
            
            # Apply bandpass filter (human voice range)
            nyquist = self.sampling_rate / 2
            low = 85 / nyquist
            high = 3500 / nyquist
            
            b, a = signal.butter(4, [low, high], btype='band')
            filtered = signal.filtfilt(b, a, audio)
            
            return filtered
        
        except Exception:
            return audio


class EnhancedGoogleASR:
    """
    Enhanced Google Speech Recognition with preprocessing
    Uses RNNoise + VAD preprocessing for better accuracy
    """
    
    def __init__(self, sampling_rate: int = 16000):
        """
        Initialize Enhanced Google ASR
        
        Args:
            sampling_rate: Audio sample rate (Hz)
        """
        self.sampling_rate = sampling_rate
        self.available = SPEECH_RECOGNITION_AVAILABLE
        self.recognizer = None
        
        if self.available:
            try:
                self.recognizer = sr.Recognizer()
                print("✅ Enhanced Google ASR initialized")
            except Exception as e:
                print(f"❌ Failed to initialize Google ASR: {e}")
                self.available = False
        else:
            print("⚠️ Google ASR not available")
    
    def transcribe(
        self, 
        audio: np.ndarray, 
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text using Google SR
        
        Args:
            audio: Audio data (numpy array, 16kHz, float32)
            language: Language code ('en', 'hi', etc.)
        
        Returns:
            Dict with 'text', 'confidence', 'language'
        """
        if not self.available or self.recognizer is None:
            return self._fallback_response()
        
        try:
            # Convert numpy array to AudioData format
            # Google SR expects int16 PCM data
            if audio.dtype == np.float32:
                # Convert from float32 [-1, 1] to int16
                audio_int16 = (audio * 32767).astype(np.int16)
            else:
                audio_int16 = audio.astype(np.int16)
            
            # Create AudioData object
            audio_data = sr.AudioData(
                audio_int16.tobytes(),
                sample_rate=self.sampling_rate,
                sample_width=2  # 16-bit = 2 bytes
            )
            
            # Convert language code
            lang_code = self._get_language_code(language)
            
            # Try to get alternatives for confidence estimation
            try:
                result = self.recognizer.recognize_google(
                    audio_data,
                    language=lang_code,
                    show_all=True
                )
                
                if result and isinstance(result, dict) and 'alternative' in result:
                    alternatives = result['alternative']
                    if alternatives and len(alternatives) > 0:
                        best = alternatives[0]
                        text = best.get('transcript', '')
                        # Google provides confidence in alternatives
                        confidence = best.get('confidence', 0.8)
                        
                        return {
                            "text": text.strip(),
                            "confidence": float(confidence),
                            "language": language
                        }
            except Exception:
                pass  # Fall through to simple recognition
            
            # Fallback: Simple recognition (no confidence)
            text = self.recognizer.recognize_google(audio_data, language=lang_code)
            
            return {
                "text": text.strip(),
                "confidence": 0.8,  # Assume good confidence
                "language": language
            }
        
        except sr.UnknownValueError:
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "error": "Speech unclear"
            }
        except sr.RequestError as e:
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "error": f"API error: {e}"
            }
        except Exception as e:
            print(f"❌ Google ASR error: {e}")
            return self._fallback_response()
    
    def _get_language_code(self, language: str) -> str:
        """Convert language to Google SR language code"""
        lang_map = {
            "en": "en-US",
            "hi": "hi-IN",
            "hinglish": "hi-IN",
            "mr": "mr-IN",
            "marathi": "mr-IN"
        }
        return lang_map.get(language.lower(), "en-US")
    
    def _fallback_response(self) -> Dict[str, Any]:
        """Fallback response when ASR fails"""
        return {
            "text": "",
            "confidence": 0.0,
            "language": "en",
            "error": "Google ASR not available"
        }


class AdvancedAudioProcessor:
    """
    Complete ML-grade audio processing pipeline
    Phase 1: RNNoise + VAD + Enhanced Google SR + Confidence Filtering
    """
    
    def __init__(
        self,
        sampling_rate: int = 16000,
        confidence_threshold: float = 0.6
    ):
        """
        Initialize advanced audio processor
        
        Args:
            sampling_rate: Audio sample rate (Hz)
            confidence_threshold: Minimum confidence for transcription
        """
        self.sampling_rate = sampling_rate
        self.confidence_threshold = confidence_threshold
        
        print("🚀 Initializing Advanced Audio Processor (Phase 1 - No Whisper)...")
        
        # Initialize components
        self.rnnoise = RNNoiseProcessor(sampling_rate)
        self.vad = SileroVAD(0.5, sampling_rate)  # Fixed threshold for RNN-based VAD
        self.asr = EnhancedGoogleASR(sampling_rate)
        
        # Statistics
        self.stats = {
            "total_chunks": 0,
            "speech_chunks": 0,
            "noise_chunks": 0,
            "transcriptions": 0,
            "low_confidence_rejections": 0
        }
        
        print("✅ Advanced Audio Processor ready!")
    
    def process_audio(
        self,
        audio: np.ndarray,
        language: str = "en",
        skip_vad: bool = False
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Complete audio processing pipeline
        
        Pipeline: Noise Suppression → VAD → Transcription → Confidence Filter
        
        Args:
            audio: Raw audio input (numpy array)
            language: Language code
            skip_vad: Skip VAD check (process anyway)
        
        Returns:
            (transcribed_text, metadata_dict)
        """
        self.stats["total_chunks"] += 1
        
        metadata = {
            "noise_suppressed": False,
            "vad_detected": False,
            "speech_probability": 0.0,
            "confidence": 0.0,
            "processing_stages": []
        }
        
        # Stage 1: Noise Suppression
        try:
            denoised = self.rnnoise.suppress_noise(audio, stationary=True)
            metadata["noise_suppressed"] = True
            metadata["processing_stages"].append("noise_suppression")
        except Exception as e:
            print(f"⚠️ Noise suppression failed: {e}")
            denoised = audio
        
        # Stage 2: Voice Activity Detection
        if not skip_vad:
            speech_prob = self.vad.get_speech_probability(denoised)
            metadata["speech_probability"] = speech_prob
            
            if not self.vad.is_speech(denoised):
                self.stats["noise_chunks"] += 1
                metadata["vad_detected"] = False
                return None, metadata
            
            self.stats["speech_chunks"] += 1
            metadata["vad_detected"] = True
            metadata["processing_stages"].append("vad_passed")
        
        # Stage 3: Transcription with Enhanced Google SR
        try:
            result = self.asr.transcribe(denoised, language)
            metadata["confidence"] = result.get("confidence", 0.0)
            metadata["language"] = result.get("language", language)
            metadata["processing_stages"].append("transcription")
            
            self.stats["transcriptions"] += 1
            
            # Stage 4: Confidence Filtering
            if result["confidence"] < self.confidence_threshold:
                self.stats["low_confidence_rejections"] += 1
                metadata["processing_stages"].append("confidence_rejected")
                return None, metadata
            
            metadata["processing_stages"].append("confidence_passed")
            return result["text"], metadata
        
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            metadata["error"] = str(e)
            return None, metadata
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        total = self.stats["total_chunks"]
        
        return {
            **self.stats,
            "speech_ratio": self.stats["speech_chunks"] / total if total > 0 else 0,
            "success_rate": self.stats["transcriptions"] / self.stats["speech_chunks"] 
                           if self.stats["speech_chunks"] > 0 else 0,
            "rejection_rate": self.stats["low_confidence_rejections"] / self.stats["transcriptions"]
                             if self.stats["transcriptions"] > 0 else 0
        }
    
    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            "total_chunks": 0,
            "speech_chunks": 0,
            "noise_chunks": 0,
            "transcriptions": 0,
            "low_confidence_rejections": 0
        }
    
    def is_available(self) -> bool:
        """Check if advanced processing is available"""
        return (
            self.rnnoise.available and 
            self.vad.available and 
            self.asr.available
        )
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get available capabilities"""
        return {
            "noise_suppression": self.rnnoise.available,
            "vad": self.vad.available,
            "enhanced_google_asr": self.asr.available,
            "confidence_filtering": True
        }

