# 🤖 MICROBOT Deployment Guide

Complete guide to deploy the Microbot system on your server and ESP32 hardware.

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Part 1: Server Deployment](#part-1-server-deployment)
3. [Part 2: ESP32 Hardware Setup](#part-2-esp32-hardware-setup)
4. [Part 3: Arduino IDE Setup](#part-3-arduino-ide-setup)
5. [Part 4: Upload Code to ESP32](#part-4-upload-code-to-esp32)
6. [Part 5: SD Card Setup](#part-5-sd-card-setup)
7. [Part 6: Testing](#part-6-testing)
8. [Troubleshooting](#troubleshooting)

---

## 🔄 System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        ESP32 Device                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ INMP441  │  │MAX98357A │  │ ILI9341  │  │ SD Card  │    │
│  │   Mic    │  │ Speaker  │  │   TFT    │  │Expression│    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
│       └─────────────┼─────────────┼─────────────┘           │
│                     │             │                          │
│              Audio I/O      Display (LOCAL)                  │
└─────────────────────┼───────────────────────────────────────┘
                      │ WiFi (HTTP)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Server (Python)                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │   STT    │  │  Gemini  │  │   TTS    │                  │
│  │ (Google) │  │   AI     │  │ (Polly)  │                  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       │             │             │                          │
│       └─────────────┼─────────────┘                          │
│                     ▼                                        │
│              /process endpoint                               │
│         (Audio in → Audio out)                              │
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Server** handles AI processing ONLY (STT → AI → TTS)
- **ESP32** handles expressions LOCALLY (no server needed for expressions!)
- ESP32 can play expressions even WITHOUT WiFi

---

## 📦 Part 1: Server Deployment

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Internet connection

### Step 1: Install Dependencies

```bash
cd "C:\Microbot\First launch"
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install these packages:

```bash
pip install fastapi uvicorn python-dotenv google-generativeai boto3 SpeechRecognition pydub numpy python-multipart httpx
```

### Step 2: Configure Environment Variables

Create a `.env` file in `C:\Microbot\First launch\`:

```env
# Google Gemini API Key (get from: https://makersuite.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# AWS Credentials for Polly TTS (get from AWS Console)
MICROBOT_AWS_ACCESS_KEY=your_aws_access_key
MICROBOT_AWS_SECRET_KEY=your_aws_secret_key
AWS_REGION=ap-south-1
```

### Step 3: Get API Keys

#### Google Gemini API Key:
1. Go to https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key to your `.env` file

#### AWS Credentials (for TTS):
1. Go to AWS Console → IAM → Users
2. Create a new user with "AmazonPollyFullAccess" permission
3. Create access key and copy to `.env` file

### Step 4: Start the Server

```bash
cd "C:\Microbot\First launch"
python api_server.py
```

You should see:

```
🚀 Initializing Microbot API Server...
✅ Config store initialized
✅ Notes manager initialized
✅ Voice system initialized (STT/TTS ready)
✅ Reminder system initialized
✅ Chat manager initialized
✅ Microbot API Server ready!
```

### Step 5: Test the Server

Open a browser and go to: `http://localhost:5000/api/health`

You should see:

```json
{
  "status": "healthy",
  "components": {
    "config": true,
    "voice": true,
    "ai": true,
    "reminders": true,
    "notes": true
  }
}
```

### Step 6: Get Your Server IP

Run this command to find your computer's IP address:

```bash
ipconfig
```

Look for "IPv4 Address" under your WiFi adapter (e.g., `192.168.1.100`).

**You'll need this IP for the ESP32 configuration!**

---

## 🔧 Part 2: ESP32 Hardware Setup

### Required Components

| Component | Purpose | Quantity |
|-----------|---------|----------|
| ESP32-WROOM-32 DevKit | Main controller | 1 |
| INMP441 Microphone | Audio input | 1 |
| MAX98357A Amplifier | Audio output | 1 |
| 3W 4Ω Speaker | Sound | 1 |
| ILI9341 2.8" TFT | Display | 1 |
| MicroSD Card Module | Expression storage | 1 |
| MicroSD Card (4GB+) | Store videos | 1 |
| TTP223 Touch Sensor | Touch input | 1 |
| 18650 Battery | Power | 1 |
| TP4056 Charger | Charging | 1 |
| Power Switch | On/Off | 1 |
| Jumper Wires | Connections | Many |

### Wiring Diagram

```
ESP32 Pin Connections:
═══════════════════════════════════════════════════════════

INMP441 Microphone:
├── VDD  → 3.3V
├── GND  → GND
├── SD   → GPIO32 (Data)
├── SCK  → GPIO27 (Shared with speaker)
├── WS   → GPIO26 (Shared with speaker)
└── L/R  → GND (IMPORTANT!)

MAX98357A Speaker Amp:
├── VIN  → 3.3V
├── GND  → GND
├── DIN  → GPIO25 (Data)
├── BCLK → GPIO27 (Shared with mic)
├── LRC  → GPIO26 (Shared with mic)
├── GAIN → 3.3V (Max volume)
├── SD   → Leave floating
└── +/-  → Speaker wires

ILI9341 TFT Display:
├── VCC   → 3.3V
├── GND   → GND
├── CS    → GPIO5
├── RESET → GPIO2
├── DC    → GPIO4
├── MOSI  → GPIO23 (Shared with SD)
├── SCK   → GPIO18 (Shared with SD)
└── LED   → GPIO15 (Backlight)

SD Card Module:
├── VCC  → 3.3V
├── GND  → GND
├── CS   → GPIO21
├── MOSI → GPIO23 (Shared with TFT)
├── MISO → GPIO19
└── SCK  → GPIO18 (Shared with TFT)

TTP223 Touch Sensor:
├── VCC → 3.3V
├── GND → GND
└── SIG → GPIO33

Power System (TP4056):
├── IN+   → USB-C 5V
├── IN-   → USB-C GND
├── B+    → Battery +
├── B-    → Battery -
├── OUT+  → Power Switch → ESP32 VIN
└── OUT-  → ESP32 GND
```

### Important Notes

1. **INMP441 L/R Pin**: MUST be connected to GND for left channel!
2. **Shared Pins**: GPIO27 and GPIO26 are shared between mic and speaker
3. **Shared SPI**: GPIO18 and GPIO23 are shared between TFT and SD card
4. **Power**: ESP32 needs 3.3V, use VIN for 5V input

---

## 💻 Part 3: Arduino IDE Setup

### Step 1: Download Arduino IDE

1. Go to https://www.arduino.cc/en/software
2. Download "Arduino IDE" (latest version)
3. Install it on your computer

### Step 2: Add ESP32 Board Support

1. Open Arduino IDE
2. Go to **File → Preferences**
3. In "Additional Board Manager URLs", add:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Click **OK**

5. Go to **Tools → Board → Boards Manager**
6. Search for "ESP32"
7. Install "**esp32** by Espressif Systems" (version 2.0.x or later)
8. Wait for installation to complete

### Step 3: Install Required Libraries

Go to **Sketch → Include Library → Manage Libraries**

Install these libraries (search and click Install):

| Library | Author | Purpose |
|---------|--------|---------|
| TFT_eSPI | Bodmer | TFT display driver |

**Note**: Other libraries (WiFi, SD, SPI) are included with ESP32 board package.

### Step 4: Configure TFT_eSPI Library

This is **CRITICAL** for the display to work!

1. Find the TFT_eSPI library folder:
   - Windows: `C:\Users\<YourName>\Documents\Arduino\libraries\TFT_eSPI\`

2. Open `User_Setup.h` in a text editor (e.g., Notepad++)

3. **Comment out** the default driver and **uncomment** ILI9341:
   ```cpp
   // #define ILI9341_DRIVER       // <-- UNCOMMENT this line
   // #define ST7735_DRIVER        // <-- Keep this commented
   ```

4. **Set the pins** - find and modify these lines:
   ```cpp
   #define TFT_MOSI 23
   #define TFT_SCLK 18
   #define TFT_CS    5
   #define TFT_DC    4
   #define TFT_RST   2
   ```

5. Save the file

---

## 📤 Part 4: Upload Code to ESP32

### Step 1: Configure Your Settings

1. Open `C:\Microbot\First launch\CLIENT_CODE\microbot_esp32.ino` in Arduino IDE

2. Edit the WiFi and Server settings at the top:
   ```cpp
   // WiFi Configuration
   const char* WIFI_SSID = "YOUR_WIFI_NAME";        // <-- Change this!
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"; // <-- Change this!

   // Server Configuration
   const char* SERVER_HOST = "192.168.1.100";  // <-- Your server IP!
   const int SERVER_PORT = 5000;
   ```

### Step 2: Select the Board

1. Connect ESP32 to your computer via USB cable
2. Go to **Tools → Board → ESP32 Arduino → "ESP32 Dev Module"**

### Step 3: Select the Port

1. Go to **Tools → Port**
2. Select the COM port that appeared when you plugged in ESP32
   - Windows: Usually "COM3", "COM4", or similar
   - If unsure, unplug ESP32, check ports, plug back in, see which one appears

### Step 4: Configure Upload Settings

Go to **Tools** and set:
- **Upload Speed**: 921600
- **Flash Frequency**: 80MHz
- **Flash Mode**: QIO
- **Flash Size**: 4MB (32Mb)
- **Partition Scheme**: Default 4MB with spiffs

### Step 5: Upload!

1. Click the **Upload** button (→ arrow icon)
2. When you see "Connecting...", press and hold the **BOOT** button on ESP32
3. Release when you see "Uploading..."
4. Wait for upload to complete (about 30 seconds)

You should see:
```
Leaving...
Hard resetting via RTS pin...
```

### Step 6: Open Serial Monitor

1. Go to **Tools → Serial Monitor**
2. Set baud rate to **115200** (bottom right)
3. Press the **EN** (reset) button on ESP32
4. You should see the startup messages!

---

## 💾 Part 5: SD Card Setup

### Step 1: Format SD Card

1. Insert SD card into your computer
2. Format as **FAT32** (not exFAT or NTFS!)
   - Right-click SD card → Format → FAT32

### Step 2: Create Expression Folders

Create this folder structure on SD card:

```
SD Card Root/
└── Expression/
    ├── Burger/
    │   └── Burger.mp4
    ├── Jungle/
    │   ├── Jungle1.mp4
    │   └── Jungle2.mp4
    ├── Love/
    │   ├── love1.mp4
    │   ├── love2.mp4
    │   └── love3.mp4
    └── Winter/
        ├── winter1.mp4
        └── winter2.mp4
```

### Step 3: Copy Expression Videos

Copy your MP4 expression videos into the appropriate folders.

**Important**: 
- Videos should be small (under 1MB each)
- Format: MP4 with H.264 encoding
- Resolution: Keep it small for TFT display

### Step 4: Insert SD Card

Insert the SD card into the SD card module connected to ESP32.

---

## ✅ Part 6: Testing

### Test 1: Server Connection

1. Start the server: `python api_server.py`
2. Power on ESP32
3. Open Serial Monitor
4. Check if it connects to WiFi and shows your IP

### Test 2: Touch to Speak

1. Ensure server is running
2. Touch the TTP223 sensor
3. Speak into the microphone
4. Listen for the AI response!

### Test 3: Expression Playback

1. Touch the sensor when WiFi is OFF
2. A random expression should play (local only!)

### Test 4: Check Server Logs

On the server, you should see:
```
📥 ESP32: Received 96000 bytes PCM
🎤 User said: "Hello"
🤖 AI Response: "Hello! How can I help you?"
📤 Sending 48000 bytes PCM to ESP32
```

---

## 🔧 Troubleshooting

### ESP32 Won't Upload

**Problem**: "A fatal error occurred: Failed to connect to ESP32"

**Solution**:
1. Press and HOLD the **BOOT** button
2. Click Upload in Arduino IDE
3. Release BOOT when you see "Connecting..."

### WiFi Won't Connect

**Problem**: ESP32 can't connect to WiFi

**Solution**:
1. Double-check SSID and password (case-sensitive!)
2. Make sure WiFi is 2.4GHz (ESP32 doesn't support 5GHz)
3. Move ESP32 closer to router

### No Sound from Speaker

**Problem**: Speaker is silent

**Solution**:
1. Check MAX98357A wiring
2. Ensure GAIN pin is connected to 3.3V
3. Check speaker connections (+/-)

### Microphone Not Working

**Problem**: "Almost all zeros" in audio analysis

**Solution**:
1. Check INMP441 wiring
2. **CRITICAL**: Ensure L/R pin is connected to GND!
3. Speak louder / closer to mic

### Display Not Working

**Problem**: TFT screen is blank

**Solution**:
1. Check User_Setup.h configuration
2. Verify TFT wiring
3. Check backlight (GPIO15) connection

### Server Connection Failed

**Problem**: ESP32 can't reach server

**Solution**:
1. Verify server IP address is correct
2. Ensure server is running (`python api_server.py`)
3. Check firewall isn't blocking port 5000
4. Both devices must be on same WiFi network

### SD Card Not Found

**Problem**: "SD card initialization failed"

**Solution**:
1. Ensure SD card is FAT32 formatted
2. Check SD card module wiring
3. Try a different SD card

---

## 🎉 Success!

If everything works:
1. ✅ ESP32 connects to WiFi
2. ✅ Touch triggers recording
3. ✅ Audio is sent to server
4. ✅ AI response plays through speaker
5. ✅ Expressions display on TFT

**Congratulations! Your Microbot is ready!** 🤖

---

## 📁 File Structure Summary

```
C:\Microbot\First launch\
├── api_server.py          # Server code (run this!)
├── .env                   # API keys (create this!)
├── requirements.txt       # Python dependencies
├── microbot/              # Core logic modules
└── CLIENT_CODE/           # ESP32 code
    ├── microbot_esp32.ino # Main ESP32 code (upload this!)
    └── microbot_config.h  # Hardware pin definitions
```

---

## 📞 Need Help?

Common issues:
- **COM port not showing**: Install CH340 or CP2102 USB driver
- **Library errors**: Reinstall libraries via Library Manager
- **Memory errors**: Close other apps, reduce audio buffer size

