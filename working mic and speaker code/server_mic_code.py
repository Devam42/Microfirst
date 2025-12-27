#!/usr/bin/env python3
"""
Microphone Test Server - Fixed Version
Receives audio → Analyzes → Transcribes → Returns result as JSON
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from io import BytesIO
import speech_recognition as sr
import wave
import os
import numpy as np

app = FastAPI()

def pcm_to_wav(pcm_data):
    """Convert PCM to WAV"""
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer.read()

def analyze_audio(pcm_data):
    """Analyze audio quality - FIXED VERSION"""
    samples = np.frombuffer(pcm_data, dtype=np.int16)

    non_zero = np.count_nonzero(samples)
    max_val = np.max(samples)
    min_val = np.min(samples)
    avg_amplitude = np.mean(np.abs(samples))

    # Fix: Handle NaN for RMS calculation
    try:
        rms_squared = np.mean(samples.astype(np.float64)**2)
        rms = float(np.sqrt(rms_squared)) if rms_squared >= 0 else 0.0
    except:
        rms = 0.0

    # Convert numpy types to Python native types (JSON serializable)
    return {
        "total_samples": int(len(samples)),
        "non_zero_samples": int(non_zero),
        "non_zero_percent": float(non_zero * 100.0 / len(samples)),
        "max_value": int(max_val),
        "min_value": int(min_val),
        "avg_amplitude": float(avg_amplitude),
        "rms_level": float(rms),
        "duration_sec": float(len(samples) / 16000.0)
    }

def speech_to_text(audio_data):
    """STT: Audio → Text"""
    recognizer = sr.Recognizer()

    # Adjust recognizer settings for better accuracy
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    audio_file = BytesIO(audio_data)

    with sr.AudioFile(audio_file) as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio, language="en-US", show_all=False)
        return True, text.strip()
    except sr.UnknownValueError:
        return False, "Speech unclear or no speech detected"
    except sr.RequestError as e:
        return False, f"Google API error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

@app.get("/")
def root():
    return {
        "status": "ready",
        "mode": "microphone_test",
        "endpoint": "POST /process",
        "info": "Send PCM audio (16kHz, mono, 16-bit) to /process"
    }

@app.post("/process")
async def process_audio(audio: UploadFile = File(...)):
    """
    Receive PCM audio → Analyze → Transcribe → Return detailed results
    """
    try:
        # Read PCM
        pcm_data = await audio.read()
        print(f"\n{'='*60}")
        print(f"📥 Received {len(pcm_data)} bytes PCM")

        # Analyze audio quality
        analysis = analyze_audio(pcm_data)
        print(f"📊 Audio Analysis:")
        print(f"   Duration: {analysis['duration_sec']:.2f} seconds")
        print(f"   Non-zero: {analysis['non_zero_percent']:.1f}%")
        print(f"   Range: {analysis['min_value']} to {analysis['max_value']}")
        print(f"   Avg amplitude: {analysis['avg_amplitude']:.1f}")
        print(f"   RMS level: {analysis['rms_level']:.1f}")

        # Quality check
        if analysis['non_zero_percent'] < 5:
            print("❌ PROBLEM: Audio is mostly silence!")
            return JSONResponse(content={
                "success": False,
                "error": "Microphone not working - only silence detected",
                "analysis": analysis,
                "suggestion": "Check: 1) L/R pin to GND, 2) Speak louder, 3) Mic connections"
            })

        if analysis['non_zero_percent'] < 50:
            print("⚠️  WARNING: Weak audio signal (might affect transcription)")

        if analysis['avg_amplitude'] < 100:
            print("⚠️  WARNING: Very low amplitude - speak louder!")

        # Convert to WAV
        wav_data = pcm_to_wav(pcm_data)

        # Speech to Text
        print("🎤 Attempting transcription...")
        success, result = speech_to_text(wav_data)

        if success:
            print(f"✅ TRANSCRIBED: '{result}'")
            print(f"{'='*60}\n")
            return JSONResponse(content={
                "success": True,
                "text": result,
                "analysis": analysis,
                "message": f"Successfully transcribed: {result}"
            })
        else:
            print(f"⚠️  STT failed: {result}")
            print(f"{'='*60}\n")
            return JSONResponse(content={
                "success": False,
                "error": result,
                "analysis": analysis,
                "suggestion": "Audio received but speech not clear. Try: 1) Speak louder, 2) Speak closer to mic, 3) Reduce background noise"
            })

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return JSONResponse(content={
            "success": False,
            "error": str(e),
            "suggestion": "Server error - check server logs"
        })

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ESP32 Microphone Test Server",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🎙️ ESP32 Microphone Test Server")
    print("=" * 60)
    print("Listening on http://0.0.0.0:8000")
    print("Endpoints:")
    print("  GET  /        - Server info")
    print("  GET  /health  - Health check")
    print("  POST /process - Process audio")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")