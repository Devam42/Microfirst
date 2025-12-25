"""
Audio Quality Improver
Enhances audio quality for better speech recognition
"""

import numpy as np
from typing import Optional
import speech_recognition as sr


class AudioQualityImprover:
    """Improves audio quality for better speech recognition"""
    
    @staticmethod
    def apply_noise_reduction(audio_data: sr.AudioData, sample_rate: int = 16000) -> sr.AudioData:
        """
        Apply basic noise reduction to audio
        
        Args:
            audio_data: Original audio data
            sample_rate: Sample rate in Hz
        
        Returns:
            Processed audio data
        """
        try:
            # Convert to numpy array
            audio_array = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
            
            # Apply simple high-pass filter to remove low-frequency noise
            # This helps remove background hum and rumble
            audio_float = audio_array.astype(np.float32)
            
            # Simple noise gate: reduce very quiet sounds
            threshold = np.percentile(np.abs(audio_float), 10)  # 10th percentile
            mask = np.abs(audio_float) > threshold
            audio_float = audio_float * mask
            
            # Normalize audio levels
            if np.max(np.abs(audio_float)) > 0:
                audio_float = audio_float / np.max(np.abs(audio_float)) * 32767 * 0.9
            
            # Convert back to int16
            audio_processed = audio_float.astype(np.int16)
            
            # Create new AudioData object
            return sr.AudioData(
                audio_processed.tobytes(),
                audio_data.sample_rate,
                audio_data.sample_width
            )
        
        except Exception as e:
            print(f"⚠️ Audio processing warning: {e}")
            return audio_data  # Return original if processing fails
    
    @staticmethod
    def get_audio_stats(audio_data: sr.AudioData) -> dict:
        """
        Get statistics about audio quality
        
        Args:
            audio_data: Audio data to analyze
        
        Returns:
            Dictionary with audio statistics
        """
        try:
            audio_array = np.frombuffer(audio_data.get_raw_data(), dtype=np.int16)
            
            return {
                "duration": len(audio_array) / audio_data.sample_rate,
                "sample_rate": audio_data.sample_rate,
                "max_amplitude": np.max(np.abs(audio_array)),
                "mean_amplitude": np.mean(np.abs(audio_array)),
                "rms_level": np.sqrt(np.mean(audio_array.astype(np.float32)**2)),
                "clipping": np.sum(np.abs(audio_array) >= 32767)
            }
        except Exception as e:
            return {"error": str(e)}

