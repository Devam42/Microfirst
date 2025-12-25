#!/usr/bin/env python3
"""
Microbot FastAPI Server
RESTful API server for Microbot AI Assistant
Provides 3 main APIs: Config, Talk, and Data
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import traceback
import threading
import time

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # This loads .env file into environment variables

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fastapi import FastAPI, HTTPException, status, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import random
import httpx
import asyncio
import google.generativeai as genai
import wave
import io
import numpy as np
from pydub import AudioSegment
from contextlib import closing
import boto3
import speech_recognition as sr

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Import Microbot components
try:
    from microbot.utils.config_store import ConfigStore
    from microbot.features.reminders import ReminderManager, ReminderStorage
    from microbot.features.notes import NotesManager
    from microbot.features.voice import VoiceManager
    from microbot.core.simple_chat_manager import SimpleChatManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all required modules are installed.")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)


# ============================================================================
# Expression Selection System - DISABLED (Will be reimplemented later)
# ============================================================================

# Expression Registry and selection function have been temporarily disabled
# They will be reimplemented with a better approach later
# For now, all API endpoints return expression: None

# ============================================================================
# Lifespan Context Manager (Startup/Shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    global config_store, reminder_manager, reminder_storage, notes_manager, voice_manager, chat_manager, wake_word_detector
    
    try:
        print("🚀 Initializing Microbot API Server...")
        
        # Initialize config store
        config_store = ConfigStore()
        print("✅ Config store initialized")
        
        # Initialize notes manager
        notes_manager = NotesManager()
        print("✅ Notes manager initialized")
        
        # Initialize voice manager (if AWS credentials available)
        try:
            voice_manager = VoiceManager(config_store=config_store)
            if voice_manager.is_available():
                print("✅ Voice system initialized (STT/TTS ready)")
            else:
                print("⚠️ Voice system partially available")
        except Exception as e:
            print(f"ℹ️ Voice system not available: {e}")
            voice_manager = None
        
        # Initialize reminder system FIRST (before chat manager)
        # This will be shared with chat_manager to prevent duplicate schedulers
        def reminder_callback(reminder_data: Dict[str, Any]):
            """Enhanced callback for reminders - adds to pending queue for voice announcement"""
            task = reminder_data.get('task', 'reminder')
            language = reminder_data.get('context', {}).get('language', 'hinglish')
            
            print(f"🔔 REMINDER TRIGGERED: {task}")
            
            # Create reminder message
            if language == "english":
                message = f"⏰ Reminder: {task}!"
            else:
                message = f"⏰ Yaad dilana: {task}!"
            
            # Add to pending_reminders list (will be spoken by background thread)
            # Note: chat_manager will be available at runtime
            if 'chat_manager' in globals() and chat_manager and hasattr(chat_manager, 'pending_reminders'):
                chat_manager.pending_reminders.append({
                    "message": message,
                    "data": reminder_data
                })
                print(f"✅ Added to pending queue: {message}")
            else:
                print(f"⚠️ Chat manager not available yet for pending queue")
            
            # Also print to console
            print(f"\n{message}\n")
        
        reminder_storage = ReminderStorage()
        reminder_manager = ReminderManager(reminder_callback)
        reminder_manager.start()
        print("✅ Reminder system initialized")
        
        # NOW initialize chat manager - pass the reminder_manager to prevent duplication
        try:
            chat_manager = SimpleChatManager(external_reminder_manager=reminder_manager)
            print("✅ Chat manager initialized")
        except Exception as e:
            print(f"❌ Chat manager initialization failed: {e}")
            chat_manager = None
        
        print("✅ Microbot API Server ready!")
        
    except Exception as e:
        print(f"❌ Startup error: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    yield  # Server runs here
    
    # Shutdown
    try:
        if reminder_manager:
            reminder_manager.stop()
            print("🔔 Reminder system stopped")
        
        print("👋 Microbot API Server shutdown complete")
        
    except Exception as e:
        print(f"⚠️ Shutdown error: {e}")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Microbot Local API Server",
    version="1.0.0",
    description="RESTful API for Microbot AI Assistant with voice conversation support",
    lifespan=lifespan
)

# Enable CORS for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Global Components (Initialize once at startup)
# ============================================================================
config_store: Optional[ConfigStore] = None
reminder_manager: Optional[ReminderManager] = None
reminder_storage: Optional[ReminderStorage] = None
notes_manager: Optional[NotesManager] = None
voice_manager: Optional[VoiceManager] = None
chat_manager: Optional[SimpleChatManager] = None

# Continuous voice mode state
continuous_voice_active = False
continuous_voice_thread = None
conversation_paused = True  # Start paused, waiting for wake word

# ============================================================================
# Webhook System (Push-based client notification)
# ============================================================================
registered_webhooks: List[str] = []  # List of client webhook URLs
webhook_lock = threading.Lock()

def register_webhook(webhook_url: str):
    """Register a client webhook URL"""
    with webhook_lock:
        if webhook_url not in registered_webhooks:
            registered_webhooks.append(webhook_url)
            print(f"✅ Webhook registered: {webhook_url}")
            return True
        return False

def unregister_webhook(webhook_url: str):
    """Unregister a client webhook URL"""
    with webhook_lock:
        if webhook_url in registered_webhooks:
            registered_webhooks.remove(webhook_url)
            print(f"❌ Webhook unregistered: {webhook_url}")
            return True
        return False

async def trigger_webhooks(expression_data: Dict[str, Any]):
    """Send expression data to all registered webhooks"""
    if not registered_webhooks:
        return
    
    with webhook_lock:
        urls = registered_webhooks.copy()
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for url in urls:
            try:
                response = await client.post(url, json=expression_data)
                if response.status_code == 200:
                    print(f"✅ Webhook triggered: {url}")
                else:
                    print(f"⚠️ Webhook failed ({response.status_code}): {url}")
            except Exception as e:
                print(f"❌ Webhook error: {url} - {e}")

# ============================================================================
# Pydantic Models (Request/Response schemas)
# ============================================================================

class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration"""
    bot_name: Optional[str] = None
    language: Optional[str] = None
    current_mode: Optional[str] = None
    password: Optional[str] = None
    voice_settings: Optional[Dict[str, Any]] = None
    force_mode_switch: Optional[bool] = False  # Force mode switch without password check


class TalkRequest(BaseModel):
    """Request model for voice conversation"""
    current_mode: str = Field(default="normal", description="Current mode (normal, notes, voice, etc.)")
    language: str = Field(default="english", description="Language (english, hinglish, marathi)")


class TestTalkRequest(BaseModel):
    """Request model for testing talk API with text input"""
    text_input: str
    language: str = "english"


class ReminderRequest(BaseModel):
    """Request model for adding a reminder"""
    task: str = Field(..., description="Task to remind about")
    trigger_time: str = Field(..., description="When to trigger (ISO format)")
    original_request: Optional[str] = None
    language: Optional[str] = "hinglish"


class NoteRequest(BaseModel):
    """Request model for adding a note"""
    content: str = Field(..., description="Note content")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for the note")


# ============================================================================
# API 1: Config API - Configuration Management
# ============================================================================

@app.get("/api/config")
async def get_config():
    """
    Get current bot configuration
    
    Returns:
        JSON with bot settings including name, language, mode, voice settings
    """
    try:
        if not config_store:
            raise HTTPException(status_code=503, detail="Config store not initialized")
        
        config_data = {
            "bot_name": config_store.data.get("bot_name", "Microbot"),
            "language": config_store.language(),
            "current_mode": config_store.get_current_mode(),
            "mode_states": config_store.get_mode_states(),
            "voice_settings": config_store.get_voice_settings(),
            "has_password": config_store.has_password()
        }
        
        return {
            "success": True,
            "config": config_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting config: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update bot configuration
    
    Args:
        request: Configuration update request
    
    Returns:
        JSON with success status and updated config
    """
    try:
        if not config_store:
            raise HTTPException(status_code=503, detail="Config store not initialized")
        
        # Update bot name
        if request.bot_name:
            config_store.set_name(request.bot_name)
        
        # Update language
        if request.language:
            if request.language.lower() in ["english", "hinglish", "marathi"]:
                new_language = request.language.lower()
                config_store.set_language(new_language)
                
                # CRITICAL: Clear AI history and update chat manager language context
                # This ensures bot responds in new language immediately
                _set_chat_language_context(new_language)
                print(f"✅ Language switched to: {new_language.upper()}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid language. Must be: english, hinglish, or marathi"
                )
        
        # Update mode
        if request.current_mode:
            if request.current_mode in ["normal", "notes", "pomodoro", "voice"]:
                config_store.set_mode(request.current_mode)
                
                # Update chat manager mode states if it exists
                if chat_manager:
                    # Update mode states
                    if hasattr(chat_manager, 'notes_mode_active'):
                        chat_manager.notes_mode_active = (request.current_mode == "notes")
                    if hasattr(chat_manager, 'pomodoro_mode_active'):
                        chat_manager.pomodoro_mode_active = (request.current_mode == "pomodoro")
                    if hasattr(chat_manager, 'voice_mode_active'):
                        chat_manager.voice_mode_active = (request.current_mode == "voice")
                
                print(f"✅ Mode switched to: {request.current_mode}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid mode. Must be: normal, notes, pomodoro, or voice"
                )
        
        # Update voice settings
        if request.voice_settings:
            if "english_voice" in request.voice_settings:
                config_store.set_english_voice(request.voice_settings["english_voice"])
            
            if "hinglish_voice" in request.voice_settings:
                config_store.set_hinglish_voice(request.voice_settings["hinglish_voice"])
            
            if "enabled" in request.voice_settings:
                config_store.set_voice_enabled(request.voice_settings["enabled"])
        
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": {
                "bot_name": config_store.data.get("bot_name"),
                "language": config_store.language(),
                "current_mode": config_store.get_current_mode()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ============================================================================
# API 2: Talk API - Voice Conversation (STT → AI → TTS)
# ============================================================================

@app.post("/api/talk")
async def talk(request: TalkRequest):
    """
    Real-time voice conversation pipeline
    
    Pipeline:
        1. Activate microphone (STT)
        2. User speaks
        3. Speech → Text
        4. AI processes message
        5. AI generates response
        6. Text → Speech (TTS)
        7. Play audio
        8. Return conversation data
    
    Args:
        request: Talk request with mode and language
    
    Returns:
        JSON with user input, AI response, and audio status
    """
    try:
        if not voice_manager:
            raise HTTPException(
                status_code=503,
                detail="Voice system not available. Please configure AWS credentials."
            )
        
        if not chat_manager:
            raise HTTPException(
                status_code=503,
                detail="Chat manager not available"
            )
        
        # Step 1: Activate voice mode
        success, message = voice_manager.activate_voice_mode(request.language)
        if not success:
            raise HTTPException(status_code=503, detail=message)
        
        # Step 2-3: Listen for speech and convert to text (STT)
        print("🎤 Listening for voice input...")
        success, user_input = voice_manager.listen_for_input(timeout=30)  # INCREASED: 30 seconds for better listening
        
        if not success:
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "error": user_input,  # Error message from STT
                    "step": "stt"
                }
            )
        
        print(f"📝 User said: {user_input}")
        
        # Step 4-5: Process with AI
        try:
            response_text = chat_manager.process_message(user_input)
        except Exception as ai_error:
            print(f"❌ AI processing error: {ai_error}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "error": f"AI processing failed: {str(ai_error)}",
                    "expression": None,
                    "step": "ai"
                }
            )
        
        # Expression selection disabled - will be handled separately later
        # expression = select_expression_for_response(response_text, user_input)
        
        print(f"🎭 Expression: None (will be handled separately)")
        
        # Step 6: Prepare expression data (no expression for now)
        expression_data = {
            "expression": None  # Expression system disabled temporarily
        }
        
        # Step 7: INSTANT PUSH - Trigger webhooks BEFORE speaking (zero-latency sync)
        await trigger_webhooks(expression_data)
        
        # Step 8-9: Convert to speech and play (TTS) - runs in parallel with expression display
        audio_played = False
        try:
            print("🔊 Speaking response...")
            audio_played = voice_manager.speak_response(response_text)
        except Exception as tts_error:
            print(f"⚠️ TTS error: {tts_error}")
            # Continue anyway - text response is still valid
        
        # Step 10: Return conversation data WITH expression (ESP32 FORMAT)
        return expression_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in talk API: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/talk/test")
async def talk_test(request: TestTalkRequest):
    """
    Test endpoint - simulates voice input with text
    Useful for local testing without microphone
    
    Args:
        request: Test request with text input
    
    Returns:
        JSON with AI response and expression data (NO audio playback)
    """
    try:
        if not chat_manager:
            raise HTTPException(status_code=503, detail="Chat manager not available")
        
        user_input = request.text_input
        print(f"📝 Test input: {user_input}")
        
        # Process with AI
        try:
            response_text = chat_manager.process_message(user_input)
        except Exception as ai_error:
            print(f"❌ AI processing error: {ai_error}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "error": f"AI processing failed: {str(ai_error)}",
                    "expression": None
                }
            )
        
        # Expression selection disabled - will be handled separately later
        # expression = select_expression_for_response(response_text, user_input)
        
        print(f"🎭 Expression: None (will be handled separately)")
        
        # Note: No actual TTS in test mode (to avoid spam)
        # Client will handle TTS by calling AWS Polly directly
        
        return {
            "expression": None  # Expression system disabled temporarily
        }
        
    except Exception as e:
        print(f"❌ Error in test talk API: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "expression": None
            }
        )


# ============================================================================
# ESP32 Hardware API - /process endpoint
# Receives PCM audio from ESP32, returns PCM audio + expression
# ============================================================================

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Convert raw PCM audio to WAV format"""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer.read()


def analyze_pcm_audio(pcm_data: bytes) -> dict:
    """Analyze PCM audio quality"""
    try:
        samples = np.frombuffer(pcm_data, dtype=np.int16)
        non_zero = np.count_nonzero(samples)
        max_val = int(np.max(samples))
        min_val = int(np.min(samples))
        avg_amplitude = float(np.mean(np.abs(samples)))
        
        try:
            rms_squared = np.mean(samples.astype(np.float64)**2)
            rms = float(np.sqrt(rms_squared)) if rms_squared >= 0 else 0.0
        except:
            rms = 0.0
        
        return {
            "total_samples": len(samples),
            "non_zero_samples": int(non_zero),
            "non_zero_percent": float(non_zero * 100.0 / len(samples)) if len(samples) > 0 else 0,
            "max_value": max_val,
            "min_value": min_val,
            "avg_amplitude": avg_amplitude,
            "rms_level": rms,
            "duration_sec": float(len(samples) / 16000.0)
        }
    except Exception as e:
        return {"error": str(e)}


def speech_to_text_from_wav(wav_data: bytes, language: str = "en-US") -> tuple:
    """Convert WAV audio to text using Google Speech Recognition"""
    try:
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8
        
        audio_file = io.BytesIO(wav_data)
        
        with sr.AudioFile(audio_file) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.record(source)
        
        text = recognizer.recognize_google(audio, language=language, show_all=False)
        return True, text.strip()
    except sr.UnknownValueError:
        return False, "Speech unclear or no speech detected"
    except sr.RequestError as e:
        return False, f"Google API error: {e}"
    except Exception as e:
        return False, f"STT Error: {e}"


def text_to_speech_pcm(text: str, voice_id: str = "Justin", language: str = "english") -> bytes:
    """Convert text to PCM audio using AWS Polly"""
    try:
        # Get AWS credentials
        aws_access_key = os.getenv("MICROBOT_AWS_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("MICROBOT_AWS_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "ap-south-1")
        
        if not aws_access_key or not aws_secret_key:
            print("⚠️ AWS credentials not configured for TTS")
            return b''
        
        polly = boto3.client(
            'polly',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        # Select voice based on language
        if language.lower() in ["hinglish", "hindi", "marathi"]:
            voice_id = "Aditi"
            engine = "standard"
        else:
            voice_id = voice_id if voice_id else "Justin"
            engine = "standard"
        
        # Escape special characters for SSML
        text_escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Synthesize speech with faster rate
        response = polly.synthesize_speech(
            Text=f'<speak><prosody rate="125%">{text_escaped}</prosody></speak>',
            TextType='ssml',
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine=engine
        )
        
        mp3_data = b''
        if "AudioStream" in response:
            with closing(response["AudioStream"]) as stream:
                mp3_data = stream.read()
        
        if not mp3_data:
            return b''
        
        # Convert MP3 to PCM (16kHz, mono, 16-bit)
        audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        
        # Normalize and boost volume
        audio = audio.apply_gain(-audio.max_dBFS)
        audio = audio + 6  # Boost by 6dB
        
        return audio.raw_data
        
    except Exception as e:
        print(f"❌ TTS Error: {e}")
        traceback.print_exc()
        return b''




@app.post("/process")
async def process_esp32_audio(audio: UploadFile = File(...)):
    """
    ESP32 Hardware Audio Processing Endpoint
    
    Receives raw PCM audio from ESP32 (INMP441 microphone),
    processes it through: STT → AI → TTS pipeline,
    and returns PCM audio response for MAX98357A speaker.
    
    NOTE: Expressions are handled LOCALLY on ESP32 (not from server!)
    
    Audio Format:
        Input: PCM, 16kHz, mono, 16-bit signed
        Output: PCM, 16kHz, mono, 16-bit signed
    
    Headers in Response:
        X-Transcription: What the user said
        X-Response-Text: AI response text
        X-Success: "true" or "false"
    """
    try:
        # Read PCM audio from ESP32
        pcm_data = await audio.read()
        print(f"\n{'='*60}")
        print(f"📥 ESP32: Received {len(pcm_data)} bytes PCM")
        
        # Analyze audio quality
        analysis = analyze_pcm_audio(pcm_data)
        print(f"📊 Audio Analysis:")
        print(f"   Duration: {analysis.get('duration_sec', 0):.2f} seconds")
        print(f"   Non-zero: {analysis.get('non_zero_percent', 0):.1f}%")
        print(f"   Avg amplitude: {analysis.get('avg_amplitude', 0):.1f}")
        
        # Check for silence/bad audio
        if analysis.get('non_zero_percent', 0) < 5:
            print("❌ Audio is mostly silence!")
            error_pcm = text_to_speech_pcm("Sorry, I didn't hear anything. Please try again.", language="english")
            return Response(
                content=error_pcm,
                media_type="audio/pcm",
                headers={
                    "X-Transcription": "",
                    "X-Response-Text": "Sorry, I didn't hear anything. Please try again.",
                    "X-Success": "false"
                }
            )
        
        # Convert PCM to WAV for speech recognition
        wav_data = pcm_to_wav(pcm_data)
        
        # Get language from config
        current_language = config_store.language() if config_store else "english"
        lang_code = "hi-IN" if current_language in ["hinglish", "hindi"] else "en-US"
        
        # Speech to Text
        print("🎤 Transcribing...")
        success, transcription = speech_to_text_from_wav(wav_data, language=lang_code)
        
        if not success:
            print(f"⚠️ STT failed: {transcription}")
            error_pcm = text_to_speech_pcm("Sorry, I couldn't understand. Please speak clearly.", language=current_language)
            return Response(
                content=error_pcm,
                media_type="audio/pcm",
                headers={
                    "X-Transcription": "",
                    "X-Response-Text": "Sorry, I couldn't understand. Please speak clearly.",
                    "X-Success": "false"
                }
            )
        
        print(f"🎤 User said: \"{transcription}\"")
        
        # Process with AI (using chat_manager from microbot)
        if not chat_manager:
            print("❌ Chat manager not available")
            error_pcm = text_to_speech_pcm("Sorry, AI is not available right now.", language=current_language)
            return Response(
                content=error_pcm,
                media_type="audio/pcm",
                headers={
                    "X-Transcription": transcription,
                    "X-Response-Text": "Sorry, AI is not available right now.",
                    "X-Success": "false"
                }
            )
        
        try:
            response_text = chat_manager.process_message(transcription)
            print(f"🤖 AI Response: \"{response_text}\"")
        except Exception as ai_error:
            print(f"❌ AI Error: {ai_error}")
            response_text = "Sorry, I had trouble processing that." if current_language == "english" else "Maaf kijiye, kuch problem hui."
        
        # Expression is handled locally on ESP32 - not from server
        print(f"🎭 Expression: Handled locally on ESP32")
        
        # Text to Speech (convert response to PCM audio)
        print("🔊 Generating speech...")
        tts_pcm = text_to_speech_pcm(response_text, language=current_language)
        
        if not tts_pcm:
            print("⚠️ TTS failed, sending empty audio")
            tts_pcm = b'\x00' * 1600  # 0.1 second of silence
        
        print(f"📤 Sending {len(tts_pcm)} bytes PCM to ESP32")
        print(f"{'='*60}\n")
        
        # Return PCM audio (expression is handled locally on ESP32)
        return Response(
            content=tts_pcm,
            media_type="audio/pcm",
            headers={
                "X-Transcription": transcription[:100],  # Limit header size
                "X-Response-Text": response_text[:200],  # Limit header size
                "X-Success": "true"
            }
        )
        
    except Exception as e:
        print(f"❌ Process error: {e}")
        traceback.print_exc()
        
        # Return error audio
        error_pcm = text_to_speech_pcm("Sorry, something went wrong.", language="english")
        return Response(
            content=error_pcm if error_pcm else b'\x00' * 1600,
            media_type="audio/pcm",
            headers={
                "X-Transcription": "",
                "X-Response-Text": f"Error: {str(e)}",
                "X-Success": "false"
            }
        )


# ============================================================================
# API 3: Data API - CRUD Operations
# ============================================================================

# ===== Reminders Endpoints =====

@app.get("/api/data/reminders")
async def get_reminders():
    """
    Get all active reminders
    
    Returns:
        JSON with list of active reminders
    """
    try:
        if not reminder_storage:
            raise HTTPException(status_code=503, detail="Reminder system not initialized")
        
        reminders = reminder_storage.get_active_reminders()
        
        return {
            "success": True,
            "reminders": reminders,
            "count": len(reminders)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting reminders: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/data/reminders")
async def add_reminder(request: ReminderRequest):
    """
    Add a new reminder
    
    Args:
        request: Reminder request with task and trigger time
    
    Returns:
        JSON with success status and reminder ID
    """
    try:
        if not reminder_storage or not reminder_manager:
            raise HTTPException(status_code=503, detail="Reminder system not initialized")
        
        # Parse trigger time
        try:
            trigger_time = datetime.fromisoformat(request.trigger_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid trigger_time format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
        
        # Add reminder to storage
        reminder_id = reminder_storage.add_reminder(
            task=request.task,
            trigger_time=trigger_time,
            original_request=request.original_request or request.task,
            language=request.language
        )
        
        # Schedule the reminder
        reminder_manager.get_scheduler().schedule_reminder(reminder_id, trigger_time)
        
        return {
            "success": True,
            "reminder_id": reminder_id,
            "message": "Reminder added successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error adding reminder: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ===== Notes Endpoints =====

@app.get("/api/data/notes")
async def get_notes():
    """
    Get all notes
    
    Returns:
        JSON with list of notes
    """
    try:
        if not notes_manager:
            raise HTTPException(status_code=503, detail="Notes system not initialized")
        
        notes = notes_manager.data.get("notes", [])
        
        return {
            "success": True,
            "notes": notes,
            "count": len(notes)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting notes: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/data/notes")
async def add_note(request: NoteRequest):
    """
    Add a new note
    
    Args:
        request: Note request with content and optional tags
    
    Returns:
        JSON with success status
    """
    try:
        if not notes_manager:
            raise HTTPException(status_code=503, detail="Notes system not initialized")
        
        success, message = notes_manager.add_note(
            content=request.content,
            tags=request.tags
        )
        
        if success:
            return {
                "success": True,
                "message": message
            }
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": message}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error adding note: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        JSON with health status of all components
    """
    try:
        components_status = {
            "config": config_store is not None,
            "voice": voice_manager is not None and voice_manager.is_available(),
            "ai": chat_manager is not None,
            "reminders": reminder_manager is not None,
            "notes": notes_manager is not None
        }
        
        all_healthy = all(components_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.now().isoformat(),
            "components": components_status
        }
        
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


@app.get("/api/info")
async def api_info():
    """
    API information endpoint
    
    Returns:
        JSON with API details and available endpoints
    """
    return {
        "name": "Microbot Local API Server",
        "version": "1.0.0",
        "endpoints": {
            "config": {
                "GET /api/config": "Get bot configuration",
                "PUT /api/config": "Update bot configuration"
            },
            "talk": {
                "POST /api/talk": "Real-time voice conversation (PC mic/speaker)",
                "POST /api/talk/test": "Test with text input (no audio)"
            },
            "esp32": {
                "POST /process": "ESP32 audio processing (PCM in → PCM out + expression)"
            },
            "webhook": {
                "POST /api/webhook/register": "Register client webhook URL",
                "POST /api/webhook/unregister": "Unregister client webhook URL",
                "GET /api/webhook/list": "List all registered webhooks"
            },
            "data": {
                "GET /api/data/reminders": "Get all reminders",
                "POST /api/data/reminders": "Add reminder",
                "GET /api/data/notes": "Get all notes",
                "POST /api/data/notes": "Add note"
            },
            "utility": {
                "GET /api/health": "Health check",
                "GET /api/info": "API information"
            }
        }
    }


# ============================================================================
# Webhook Registration API
# ============================================================================

class WebhookRequest(BaseModel):
    """Request model for webhook registration"""
    webhook_url: str = Field(..., description="Client webhook URL")


@app.post("/api/webhook/register")
async def register_webhook_endpoint(request: WebhookRequest):
    """
    Register a client webhook URL for push notifications
    
    Args:
        request: Webhook request with URL
    
    Returns:
        JSON with registration status
    """
    try:
        success = register_webhook(request.webhook_url)
        
        if success:
            return {
                "success": True,
                "message": "Webhook registered successfully",
                "webhook_url": request.webhook_url
            }
        else:
            return {
                "success": False,
                "message": "Webhook already registered",
                "webhook_url": request.webhook_url
            }
    
    except Exception as e:
        print(f"❌ Error registering webhook: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/webhook/unregister")
async def unregister_webhook_endpoint(request: WebhookRequest):
    """
    Unregister a client webhook URL
    
    Args:
        request: Webhook request with URL
    
    Returns:
        JSON with unregistration status
    """
    try:
        success = unregister_webhook(request.webhook_url)
        
        if success:
            return {
                "success": True,
                "message": "Webhook unregistered successfully",
                "webhook_url": request.webhook_url
            }
        else:
            return {
                "success": False,
                "message": "Webhook not found",
                "webhook_url": request.webhook_url
            }
    
    except Exception as e:
        print(f"❌ Error unregistering webhook: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/webhook/list")
async def list_webhooks():
    """
    List all registered webhook URLs
    
    Returns:
        JSON with list of webhooks
    """
    try:
        with webhook_lock:
            webhooks = registered_webhooks.copy()
        
        return {
            "success": True,
            "webhooks": webhooks,
            "count": len(webhooks)
        }
    
    except Exception as e:
        print(f"❌ Error listing webhooks: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/talk/continuous/start")
async def start_continuous_talk(request: TalkRequest):
    """
    Start continuous voice conversation mode
    
    The bot will continuously listen and respond until stopped.
    
    Returns immediately but conversation continues in background.
    """
    global continuous_voice_active, continuous_voice_thread
    
    try:
        if continuous_voice_active:
            return {
                "success": False,
                "error": "Continuous mode already running",
                "message": "Use /api/talk/continuous/stop to stop it first"
            }
        
        if not voice_manager:
            raise HTTPException(
                status_code=503,
                detail="Voice system not available"
            )
        
        if not chat_manager:
            raise HTTPException(
                status_code=503,
                detail="Chat manager not available"
            )
        
        # Start continuous conversation in background thread
        continuous_voice_active = True
        continuous_voice_thread = threading.Thread(
            target=_continuous_voice_loop,
            args=(request.current_mode, request.language),
            daemon=True
        )
        continuous_voice_thread.start()
        
        print(f"🔄 Started continuous voice mode (language: {request.language}, mode: {request.current_mode})")
        
        return {
            "success": True,
            "message": "Continuous voice mode started",
            "mode": request.current_mode,
            "language": request.language,
            "status": "running",
            "info": "Bot will continuously listen and respond until stopped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting continuous mode: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/talk/continuous/stop")
async def stop_continuous_talk():
    """
    Stop continuous voice conversation mode
    
    Returns:
        JSON with stop confirmation
    """
    global continuous_voice_active, continuous_voice_thread
    
    try:
        if not continuous_voice_active:
            return {
                "success": False,
                "message": "Continuous mode is not running"
            }
        
        # Stop the loop
        continuous_voice_active = False
        
        # Wait for thread to finish (max 5 seconds)
        if continuous_voice_thread:
            continuous_voice_thread.join(timeout=5)
            continuous_voice_thread = None
        
        print("🛑 Stopped continuous voice mode")
        
        return {
            "success": True,
            "message": "Continuous voice mode stopped"
        }
        
    except Exception as e:
        print(f"❌ Error stopping continuous mode: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/talk/continuous/status")
async def get_continuous_status():
    """
    Get status of continuous voice mode
    
    Returns:
        JSON with current status
    """
    global conversation_paused
    return {
        "success": True,
        "active": continuous_voice_active,
        "conversation_paused": conversation_paused if continuous_voice_active else True,
        "status": "running" if continuous_voice_active else "stopped",
        "language": config_store.language() if config_store else "english",
        "mode": config_store.get_current_mode() if config_store else "normal"
    }




def _check_and_speak_reminders():
    """
    Background thread function that continuously checks for pending reminders
    and speaks them immediately, interrupting any ongoing process
    """
    global continuous_voice_active
    
    while continuous_voice_active:
        try:
            # Check for pending reminders every 2 seconds
            if chat_manager and hasattr(chat_manager, 'pending_reminders') and chat_manager.pending_reminders:
                print(f"\nREMINDER INTERRUPTING")
                
                # Speak ALL pending reminders
                while chat_manager.pending_reminders:
                    reminder_notification = chat_manager.pending_reminders.pop(0)
                    reminder_msg = reminder_notification.get('message', 'Reminder!')
                    reminder_data = reminder_notification.get('data', {})
                    reminder_id = reminder_data.get('id')
                    
                    print(f"{reminder_msg}")
                    
                    # Speak the reminder IMMEDIATELY (interrupts everything)
                    try:
                        if voice_manager:
                            voice_manager.speak_response(reminder_msg)
                    except Exception as e:
                        print(f"Could not speak reminder: {e}")
                    
                    # Acknowledge the reminder as completed (mark it so it won't be mentioned again)
                    if reminder_id and reminder_storage:
                        try:
                            reminder_storage.acknowledge_triggered_reminder(reminder_id)
                            print(f"✅ Reminder {reminder_id} marked as completed (won't show again)")
                        except Exception as ack_error:
                            print(f"⚠️ Could not acknowledge reminder: {ack_error}")
                    
                    time.sleep(0.3)
                
                print(f"REMINDER COMPLETE\n")
            
            # Sleep briefly before next check
            time.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            print(f"Reminder checker error: {e}")
            time.sleep(5)


def _check_and_speak_wellness():
    """
    Background thread for proactive wellness check-ins and conversation initiation
    """
    global continuous_voice_active
    
    while continuous_voice_active:
        try:
            # Check for proactive wellness messages every 30 seconds
            if chat_manager and hasattr(chat_manager, 'wellness_manager') and chat_manager.wellness_manager:
                proactive_msg = chat_manager.wellness_manager.get_proactive_message()
                
                if proactive_msg:
                    print(f"\n🌟🌟🌟 === PROACTIVE WELLNESS CHECK ===")
                    print(f"🌟 {proactive_msg}")
                    
                    # Speak the wellness message
                    try:
                        if voice_manager:
                            voice_manager.speak_response(proactive_msg)
                    except Exception as e:
                        print(f"⚠️ Could not speak wellness message: {e}")
                    
                    print(f"🌟🌟🌟 === WELLNESS CHECK COMPLETE ===\n")
            
            # Sleep longer between wellness checks (30 seconds)
            time.sleep(30)
            
        except Exception as e:
            print(f"⚠️ Wellness checker error: {e}")
            time.sleep(60)


def _check_idle_reminders():
    """
    Background thread that checks for due reminders EVERY SECOND
    Speaks reminders proactively and immediately when time is up
    """
    global continuous_voice_active
    
    spoken_reminders = set()  # Track which reminders we've already spoken
    
    while continuous_voice_active:
        try:
            # Check EVERY SECOND for maximum responsiveness
            time.sleep(1)
            
            if not reminder_storage:
                continue
            
            # Get all active reminders
            from datetime import datetime
            active_reminders = reminder_storage.get_active_reminders()
            
            if not active_reminders:
                continue
            
            now = datetime.now()
            current_language = config_store.language() if config_store else "english"
            
            # Check for overdue reminders (past their trigger time)
            for reminder in active_reminders:
                # Skip if not active
                if reminder.get('status') != 'active':
                    continue
                
                reminder_id = reminder.get('id')
                
                # Skip if we've already spoken this reminder
                if reminder_id in spoken_reminders:
                    continue
                
                trigger_time = datetime.fromisoformat(reminder["trigger_time"])
                time_diff = (now - trigger_time).total_seconds()
                
                # If reminder is overdue (past trigger time)
                if time_diff >= 0:
                    task = reminder.get('task', 'reminder')
                    
                    print(f"\n🔔 REMINDER TIME! {task}")
                    
                    # Build reminder message (SHORT for voice)
                    if current_language == "english":
                        reminder_msg = f"Reminder! {task}"
                    else:
                        reminder_msg = f"Yaad dilana! {task}"
                    
                    # SPEAK the reminder via TTS IMMEDIATELY
                    try:
                        if voice_manager:
                            print(f"🔊 Speaking reminder now...")
                            success = voice_manager.speak_response(reminder_msg)
                            if success:
                                print(f"✅ Reminder spoken successfully")
                                # Add to spoken set so we don't repeat
                                spoken_reminders.add(reminder_id)
                            else:
                                print(f"❌ TTS failed")
                    except Exception as e:
                        print(f"❌ Could not speak: {e}")
                    
                    # Mark as triggered in storage (so it won't trigger again)
                    try:
                        reminder_storage.mark_reminder_triggered(reminder_id, reminder_msg)
                        print(f"✅ Marked as triggered: {reminder_id}")
                        
                        # Immediately acknowledge it as completed (so it won't show in queries)
                        reminder_storage.acknowledge_triggered_reminder(reminder_id)
                        print(f"✅ Reminder {reminder_id} acknowledged and completed")
                    except Exception as e:
                        print(f"❌ Error marking: {e}")
            
        except Exception as e:
            print(f"⚠️ Idle reminder checker error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)


def _continuous_voice_loop(mode: str, language: str):
    """
    Background loop for continuous voice conversation
    Runs until continuous_voice_active is set to False
    """
    global continuous_voice_active
    
    try:
        # Set initial voice based on language
        current_language = language.lower()
        _set_voice_for_language(current_language)
        
        # Activate voice mode
        success, message = voice_manager.activate_voice_mode(current_language)
        if not success:
            print(f"❌ Failed to activate voice mode: {message}")
            continuous_voice_active = False
            return
        
        print(f"🎤 Continuous voice mode active - speak anytime!\n")
        
        # Start background reminder checker thread
        reminder_thread = threading.Thread(
            target=_check_and_speak_reminders,
            daemon=True
        )
        reminder_thread.start()
        print(f"🔔 Background reminder checker started")
        
        # Start background wellness checker thread
        wellness_thread = threading.Thread(
            target=_check_and_speak_wellness,
            daemon=True
        )
        wellness_thread.start()
        print(f"🌟 Background wellness checker started")
        
        # Start idle reminder checker (speaks reminders when user is idle)
        idle_reminder_thread = threading.Thread(
            target=_check_idle_reminders,
            daemon=True
        )
        idle_reminder_thread.start()
        print(f"⏰ Idle reminder checker started\n")
        
        # Main conversation loop
        print("🎤 Microphone is now listening...")
        print("💬 Speak naturally to have a conversation\n")
        
        while continuous_voice_active:
            try:
                # Listen for speech (balanced timeout for complete sentences)
                success, user_input = voice_manager.listen_for_input(timeout=8)
                
                if not success:
                    # Handle errors SILENTLY - don't spam console when user is quiet
                    # Just continue listening without printing anything
                    continue
                
                if not continuous_voice_active:
                    break
                
                # Show what was heard
                print(f"You: {user_input}")
                
                # BLOCK language switching via voice - must use app
                user_lower = user_input.lower()
                language_switch_detected = False
                
                # Detect if user is trying to switch language
                if any(word in user_lower for word in ["switch to english", "english language", "speak english", "इंग्लिश में", "english mein", "अंग्रेज़ी", "talk in english", "english में बात करो", "english mein baat", "switch to hindi", "switch to hinglish", "hindi language", "hinglish", "हिंदी में", "hindi mein", "हिन्दी", "talk in hindi", "hindi में बात करो"]):
                    language_switch_detected = True
                    
                    # Inform user to use app for language switching
                    if current_language == "hinglish":
                        response_text = "मैं अभी Hinglish में बात कर रहा हूं। Language change करने के लिए कृपया app use करें। अभी के लिए मैं Hinglish में ही बात करूंगा।"
                    else:
                        response_text = "I'm currently speaking in English. To change my language, please use the app. For now, I'll continue speaking in English only."
                    
                    print(f"🚫 Language switch blocked - user must use app")
                
                if not language_switch_detected:
                    # Process with AI
                    try:
                        # Check if language was changed via config API (external change)
                        # If so, update our local current_language variable
                        if config_store:
                            config_language = config_store.language()
                            if config_language != current_language:
                                print(f"🌍 Language changed externally via API: {current_language} → {config_language}")
                                current_language = config_language
                                # Voice will auto-update on next message
                        
                        # Ensure chat manager is using the correct language
                        if chat_manager and hasattr(chat_manager, 'config'):
                            chat_manager.config.data['language'] = current_language
                        
                        # Ensure language selector is set correctly
                        if chat_manager and hasattr(chat_manager, 'language_selector') and chat_manager.language_selector:
                            from microbot.features.language import SupportedLanguage
                            current_lang_enum = SupportedLanguage.ENGLISH if current_language == "english" else SupportedLanguage.HINGLISH
                            if chat_manager.language_selector.current_language != current_lang_enum:
                                chat_manager.language_selector.current_language = current_lang_enum
                        
                        response_text = chat_manager.process_message(user_input)
                    except Exception as ai_error:
                        print(f"❌ AI error: {ai_error}")
                        import traceback
                        traceback.print_exc()
                        if current_language == "english":
                            response_text = "Sorry, I had trouble with that. Could you try again?"
                        else:
                            response_text = "माफ करना, समझ नहीं आया। फिर से बोलिए?"
                
                if not continuous_voice_active:
                    break
                
                # Expression selection disabled - will be handled separately later
                # expression = select_expression_for_response(response_text, user_input)
                
                print(f"🎭 Expression: None (will be handled separately)")
                
                # Prepare expression data (no expression for now)
                expression_data = {
                    "expression": None  # Expression system disabled temporarily
                }
                
                # INSTANT PUSH: Trigger webhooks BEFORE speaking (for zero-latency sync)
                import asyncio
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(trigger_webhooks(expression_data))
                    loop.close()
                except Exception as webhook_error:
                    print(f"⚠️ Webhook trigger error: {webhook_error}")
                
                # Now show and speak the bot's response
                # Expression already pushed - will display simultaneously with audio!
                print(f"🤖 {response_text}\n")
                
                try:
                    voice_manager.speak_response(response_text)
                except Exception as tts_error:
                    print(f"⚠️ TTS error: {tts_error}")
                
                # No artificial pause - immediate listening for natural conversation flow
                
            except KeyboardInterrupt:
                print("\n🛑 Continuous mode interrupted")
                continuous_voice_active = False
                break
            except Exception as loop_error:
                print(f"❌ Error: {loop_error}")
                time.sleep(1)
                if not continuous_voice_active:
                    break
        
        print(f"\n🛑 Continuous voice mode stopped")
        
    except Exception as e:
        print(f"❌ Fatal error in continuous voice loop: {e}")
        traceback.print_exc()
    finally:
        continuous_voice_active = False
        if voice_manager:
            voice_manager.deactivate_voice_mode()


def _set_voice_for_language(language: str):
    """Set appropriate voice for the language"""
    try:
        if language.lower() in ["english", "en"]:
            voice_manager.set_voice("justin")
            config_store.set_current_voice("justin")
            config_store.set_english_voice("justin")
        else:  # hinglish, hindi, marathi
            voice_manager.set_voice("aditi")
            config_store.set_current_voice("aditi")
            config_store.set_hinglish_voice("aditi")
    except Exception as e:
        print(f"⚠️ Error setting voice: {e}")


def _set_chat_language_context(language: str):
    """Set language context for chat manager to respond in correct language"""
    try:
        # Update config language
        lang = language.lower()
        config_store.data['language'] = lang
        config_store.save()  # Save the language change
        
        # IMPORTANT: Also update the chat_manager's language selector
        if chat_manager and hasattr(chat_manager, 'language_selector') and chat_manager.language_selector:
            from microbot.features.language import SupportedLanguage
            if lang == "english":
                chat_manager.language_selector.set_language(SupportedLanguage.ENGLISH)
                print(f"   ✅ Chat language set to: ENGLISH")
            else:
                chat_manager.language_selector.set_language(SupportedLanguage.HINGLISH)
                print(f"   ✅ Chat language set to: HINGLISH")
        
        # CRITICAL: Clear AI history to enforce new language from next message
        # This ensures the AI starts fresh with the new language context
        if chat_manager and hasattr(chat_manager, 'history'):
            chat_manager.history = []
            print(f"   🔄 AI conversation history cleared for language switch")
            
        # Also update the config object in chat_manager
        if chat_manager and hasattr(chat_manager, 'config'):
            chat_manager.config.data['language'] = lang
            chat_manager.config.save()
            
    except Exception as e:
        print(f"⚠️ Error setting language context: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Microbot API Server",
        "version": "1.0.0",
        "status": "running",
        "continuous_voice": "running" if continuous_voice_active else "stopped",
        "docs": "/docs",
        "info": "/api/info"
    }


# ============================================================================
# Main - Run the server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🤖 Microbot FastAPI Server")
    print("=" * 60)
    print("Starting server on http://localhost:5000")
    print("API Documentation: http://localhost:5000/docs")
    print("API Info: http://localhost:5000/api/info")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info"
    )

