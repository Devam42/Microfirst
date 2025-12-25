"""
Voice Module - Speech-to-Text and Text-to-Speech
PHASE 1 UPGRADE: ML-grade audio processing with RNNoise, VAD, and Whisper
"""

from .voice_manager import VoiceManager
from .tts_manager import TTSManager
from .stt_manager import STTManager
from .audio_config import AudioProcessingConfig, get_config_for_environment

__all__ = [
    "VoiceManager",
    "TTSManager", 
    "STTManager",
    "AudioProcessingConfig",
    "get_config_for_environment"
]

