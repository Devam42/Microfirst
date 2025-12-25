"""
Audio Configuration Module
Configuration options for PHASE 1 advanced audio processing
"""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class AudioProcessingConfig:
    """Configuration for PHASE 1 audio processing features"""
    
    # Enable/disable advanced processing
    enabled: bool = True
    
    # Noise suppression settings
    noise_suppression_enabled: bool = True
    noise_suppression_strength: float = 0.8  # 0.0-1.0 (higher = more aggressive)
    stationary_noise: bool = True  # Assume stationary noise (fan, AC)
    
    # Voice Activity Detection (VAD) settings
    vad_enabled: bool = True
    vad_threshold: float = 0.5  # 0.0-1.0 (lower = more sensitive)
    vad_sampling_rate: int = 16000  # Hz
    
    # Whisper ASR settings
    whisper_enabled: bool = True
    whisper_model: str = "base"  # tiny, base, small, medium, large
    whisper_device: str = "cpu"  # cpu or cuda
    
    # Confidence filtering
    confidence_filtering_enabled: bool = True
    confidence_threshold: float = 0.6  # 0.0-1.0 (minimum confidence to accept)
    
    # Performance settings
    sampling_rate: int = 16000  # Hz
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "enabled": self.enabled,
            "noise_suppression": {
                "enabled": self.noise_suppression_enabled,
                "strength": self.noise_suppression_strength,
                "stationary": self.stationary_noise
            },
            "vad": {
                "enabled": self.vad_enabled,
                "threshold": self.vad_threshold,
                "sampling_rate": self.vad_sampling_rate
            },
            "whisper": {
                "enabled": self.whisper_enabled,
                "model": self.whisper_model,
                "device": self.whisper_device
            },
            "confidence": {
                "enabled": self.confidence_filtering_enabled,
                "threshold": self.confidence_threshold
            },
            "sampling_rate": self.sampling_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioProcessingConfig':
        """Create config from dictionary"""
        return cls(
            enabled=data.get("enabled", True),
            noise_suppression_enabled=data.get("noise_suppression", {}).get("enabled", True),
            noise_suppression_strength=data.get("noise_suppression", {}).get("strength", 0.8),
            stationary_noise=data.get("noise_suppression", {}).get("stationary", True),
            vad_enabled=data.get("vad", {}).get("enabled", True),
            vad_threshold=data.get("vad", {}).get("threshold", 0.5),
            vad_sampling_rate=data.get("vad", {}).get("sampling_rate", 16000),
            whisper_enabled=data.get("whisper", {}).get("enabled", True),
            whisper_model=data.get("whisper", {}).get("model", "base"),
            whisper_device=data.get("whisper", {}).get("device", "cpu"),
            confidence_filtering_enabled=data.get("confidence", {}).get("enabled", True),
            confidence_threshold=data.get("confidence", {}).get("threshold", 0.6),
            sampling_rate=data.get("sampling_rate", 16000)
        )
    
    @classmethod
    def get_preset(cls, preset_name: str) -> 'AudioProcessingConfig':
        """
        Get predefined configuration preset
        
        Presets:
        - 'high_quality': Best accuracy, slower (medium model, aggressive noise reduction)
        - 'balanced': Good accuracy, good speed (base model, balanced settings) [DEFAULT]
        - 'fast': Fast processing, acceptable accuracy (tiny model, light processing)
        - 'noisy_environment': Optimized for very noisy environments
        - 'quiet_environment': Optimized for quiet environments
        """
        presets = {
            "high_quality": cls(
                enabled=True,
                noise_suppression_strength=0.9,
                vad_threshold=0.4,
                whisper_model="small",
                confidence_threshold=0.7
            ),
            "balanced": cls(
                enabled=True,
                noise_suppression_strength=0.8,
                vad_threshold=0.5,
                whisper_model="base",
                confidence_threshold=0.6
            ),
            "fast": cls(
                enabled=True,
                noise_suppression_strength=0.6,
                vad_threshold=0.6,
                whisper_model="tiny",
                confidence_threshold=0.5
            ),
            "noisy_environment": cls(
                enabled=True,
                noise_suppression_enabled=True,
                noise_suppression_strength=0.95,
                stationary_noise=False,  # Non-stationary noise
                vad_enabled=True,
                vad_threshold=0.3,  # More sensitive
                whisper_model="base",
                confidence_threshold=0.5  # Lower threshold for noisy env
            ),
            "quiet_environment": cls(
                enabled=True,
                noise_suppression_enabled=False,  # Not needed
                vad_enabled=True,
                vad_threshold=0.7,  # Less sensitive
                whisper_model="tiny",  # Can use faster model
                confidence_threshold=0.7  # Higher threshold
            )
        }
        
        return presets.get(preset_name, presets["balanced"])
    
    def get_description(self) -> str:
        """Get human-readable description of current config"""
        if not self.enabled:
            return "Advanced audio processing: DISABLED (using standard Google SR)"
        
        features = []
        if self.noise_suppression_enabled:
            features.append(f"Noise Suppression ({self.noise_suppression_strength:.0%})")
        if self.vad_enabled:
            features.append(f"VAD (threshold: {self.vad_threshold:.1f})")
        if self.whisper_enabled:
            features.append(f"Whisper ({self.whisper_model})")
        if self.confidence_filtering_enabled:
            features.append(f"Confidence Filter (>{self.confidence_threshold:.0%})")
        
        return f"PHASE 1 ML Audio: {', '.join(features)}"


# Default configuration
DEFAULT_CONFIG = AudioProcessingConfig.get_preset("balanced")


# Quick access to presets
def get_config_for_environment(environment: str) -> AudioProcessingConfig:
    """
    Get recommended config for specific environment
    
    Args:
        environment: 'noisy', 'quiet', 'normal'
    
    Returns:
        AudioProcessingConfig
    """
    env_map = {
        "noisy": "noisy_environment",
        "quiet": "quiet_environment",
        "normal": "balanced"
    }
    
    preset = env_map.get(environment.lower(), "balanced")
    return AudioProcessingConfig.get_preset(preset)


