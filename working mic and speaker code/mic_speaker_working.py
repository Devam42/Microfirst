#!/usr/bin/env python3
"""
Voice Echo Server with TTS
STT → Echo back same text → TTS (gTTS or Polly Justin voice)
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import Response
from pydub import AudioSegment
from io import BytesIO
import speech_recognition as sr
import wave
import os
import boto3
from contextlib import closing

app = FastAPI()

# AWS Polly setup (optional)
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY = ("AKIAXH6UEFXTCKGY7INH")
AWS_SECRET_KEY = ("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")

USE_POLLY = bool(AWS_ACCESS_KEY and AWS_SECRET_KEY)

if USE_POLLY:
    polly = boto3.client(
        'polly',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )
    print("✅ Using Amazon Polly (Justin voice)")
else:
    print("✅ Using gTTS (free)")

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

def speech_to_text(audio_data):
    """STT: Audio → Text"""
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    audio_file = BytesIO(audio_data)

    with sr.AudioFile(audio_file) as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio, language="en-US")
        return True, text.strip()
    except:
        return False, "Could not understand"

def text_to_speech_gtts(text):
    """TTS with gTTS → PCM"""
    from gtts import gTTS

    mp3_buf = BytesIO()
    tts = gTTS(text=text, lang="en")
    tts.write_to_fp(mp3_buf)
    mp3_buf.seek(0)

    audio = AudioSegment.from_file(mp3_buf, format="mp3")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    audio = audio.apply_gain(-audio.max_dBFS)
    audio = audio + 6

    return audio.raw_data

def text_to_speech_polly(text):
    """TTS with Polly Justin voice → PCM"""
    text_escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    response = polly.synthesize_speech(
        Text=f'<speak><prosody rate="125%">{text_escaped}</prosody></speak>',
        TextType='ssml',
        OutputFormat='mp3',
        VoiceId='Justin',
        Engine='standard'
    )

    mp3_data = b''
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            mp3_data = stream.read()

    audio = AudioSegment.from_file(BytesIO(mp3_data), format="mp3")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    audio = audio.apply_gain(-audio.max_dBFS)
    audio = audio + 6

    return audio.raw_data

@app.get("/")
def root():
    return {
        "status": "ready",
        "mode": "voice_echo",
        "tts": "Polly (Justin)" if USE_POLLY else "gTTS"
    }

@app.post("/process")
async def process_audio(audio: UploadFile = File(...)):
    """
    Receive audio → Transcribe → Echo back as speech
    """
    try:
        pcm_data = await audio.read()
        print(f"\n{'='*60}")
        print(f"📥 Received {len(pcm_data)} bytes PCM")

        wav_data = pcm_to_wav(pcm_data)
        success, text = speech_to_text(wav_data)

        if not success:
            text = "I did not hear anything"

        print(f"🎤 Heard: '{text}'")
        print(f"🔊 Speaking back: '{text}'")

        # Convert to speech
        if USE_POLLY:
            pcm_response = text_to_speech_polly(text)
        else:
            pcm_response = text_to_speech_gtts(text)

        print(f"📤 Sending {len(pcm_response)} bytes PCM")
        print(f"{'='*60}\n")

        return Response(content=pcm_response, media_type="audio/pcm")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

        error_text = "Error processing audio"
        if USE_POLLY:
            error_pcm = text_to_speech_polly(error_text)
        else:
            error_pcm = text_to_speech_gtts(error_text)

        return Response(content=error_pcm, media_type="audio/pcm")

if __name__ == "__main__":
    import uvicorn
    print("🎙️ Voice Echo Server")
    print("Speak → Hear back in Justin voice!")
    uvicorn.run(app, host="0.0.0.0", port=8000)