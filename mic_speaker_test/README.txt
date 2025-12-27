================================================================================
                    MIC & SPEAKER CONNECTION TEST
                         For MICROBOT Project
================================================================================

This folder contains test code to verify your INMP441 microphone and MAX98357A 
speaker connections before integrating with the full Microbot system.

================================================================================
                           HARDWARE REQUIRED
================================================================================

1. ESP32 DevKit (ESP32-WROOM-32)
2. INMP441 I2S MEMS Microphone
3. MAX98357A I2S Amplifier
4. Speaker (3W-5W, 4Ω or 8Ω)
5. Jumper wires (colors recommended below)
6. Breadboard (optional)

================================================================================
                         WIRING CONNECTIONS
================================================================================

INMP441 MICROPHONE
──────────────────────────────────────────────────────────────────────────────
  INMP441 Pin    ESP32 Pin     Wire Color     Notes
  ─────────────────────────────────────────────────────────────────────────────
  VDD            3.3V          RED            Power supply (3.3V only!)
  GND            GND           BLACK          Ground
  SCK            GPIO 27       YELLOW         Bit clock (shared with speaker)
  WS             GPIO 26       ORANGE         Word select (shared with speaker)
  SD             GPIO 32       BLUE           Data OUT from microphone
  L/R            GND           BLACK          ⚠️ CRITICAL: Must be grounded!
  ─────────────────────────────────────────────────────────────────────────────

  ⚠️ IMPORTANT: The L/R pin MUST be connected to GND!
     - This selects LEFT channel
     - If floating or HIGH, you will get SILENCE (all zeros)


MAX98357A SPEAKER AMPLIFIER
──────────────────────────────────────────────────────────────────────────────
  MAX98357A Pin  ESP32 Pin     Wire Color     Notes
  ─────────────────────────────────────────────────────────────────────────────
  VIN            3.3V          RED            Power (can use 5V for louder)
  GND            GND           BLACK          Ground
  BCLK           GPIO 27       YELLOW         Bit clock (shared with mic)
  LRC            GPIO 26       ORANGE         Left/Right clock (shared with mic)
  DIN            GPIO 25       GREEN          Data IN to amplifier
  GAIN           Float/3.3V    -              Float=9dB, 3.3V=15dB (loudest)
  SD             Float         -              Leave unconnected (amp enabled)
  +              Speaker +     RED            Positive speaker terminal
  -              Speaker -     BLACK          Negative speaker terminal
  ─────────────────────────────────────────────────────────────────────────────

  ⚠️ IMPORTANT: Do NOT connect the SD (shutdown) pin to GND!
     - Grounding SD will DISABLE the amplifier
     - Leave it floating (unconnected) or connect to 3.3V


================================================================================
                         WIRE COLOR SUMMARY
================================================================================

  Color          Signal Type            Used For
  ─────────────────────────────────────────────────────────────────────────────
  🔴 RED         Power (3.3V/5V)        VDD, VIN, Speaker +
  ⚫ BLACK       Ground (GND)           GND, L/R, Speaker -
  🟡 YELLOW      Clock (SCK/BCLK)       GPIO 27 to both modules
  🟠 ORANGE      Word Select (WS/LRC)   GPIO 26 to both modules
  🔵 BLUE        Mic Data (SD)          GPIO 32 from INMP441
  🟢 GREEN       Speaker Data (DIN)     GPIO 25 to MAX98357A
  ─────────────────────────────────────────────────────────────────────────────


================================================================================
                           VISUAL DIAGRAM
================================================================================

                            ESP32 DevKit
                          ┌──────────────┐
                          │              │
                          │         3.3V─┼──🔴──┬──VDD (INMP441)
                          │              │      └──VIN (MAX98357A)
                          │              │
                          │          GND─┼──⚫──┬──GND (INMP441)
                          │              │      ├──L/R (INMP441) ⚠️CRITICAL
                          │              │      └──GND (MAX98357A)
                          │              │
                          │      GPIO 27─┼──🟡──┬──SCK (INMP441)
                          │              │      └──BCLK (MAX98357A)
                          │              │
                          │      GPIO 26─┼──🟠──┬──WS (INMP441)
                          │              │      └──LRC (MAX98357A)
                          │              │
                          │      GPIO 32─┼──🔵────SD (INMP441)
                          │              │
                          │      GPIO 25─┼──🟢────DIN (MAX98357A)
                          │              │
                          │       GPIO 0─┼────── BOOT Button (built-in)
                          │              │
                          └──────────────┘

                                          MAX98357A
                                         ┌─────────┐
                                         │ +  ─────┼──🔴──┐
                                         │ -  ─────┼──⚫──┼── 🔊 Speaker
                                         └─────────┘      │


================================================================================
                           HOW TO TEST
================================================================================

1. UPLOAD THE CODE
   - Open mic_speaker_test.ino in Arduino IDE
   - Select Board: "ESP32 Dev Module"
   - Select correct COM port
   - Click Upload

2. OPEN SERIAL MONITOR
   - Set baud rate to 115200
   - You will see the test menu

3. RUN TESTS
   Type a number and press Enter:
   
   1 = Test WiFi connection
   2 = Test server connectivity
   3 = Test microphone (records 3 seconds, analyzes audio)
   4 = Test speaker (plays 440Hz beep)
   5 = Full round-trip (record → server → playback)
   A = Run all tests
   
   Or press the BOOT button to run full test

4. INTERPRET RESULTS
   - Each test shows PASS or FAIL
   - Microphone test shows audio analysis:
     * Non-zero %: Should be > 50% when speaking
     * Amplitude: Should be > 100 when speaking normally
   - Speaker test: You should hear a beep


================================================================================
                           TROUBLESHOOTING
================================================================================

PROBLEM: Microphone shows all zeros (0% non-zero)
SOLUTION: 
  ✓ Check INMP441 L/R pin is connected to GND
  ✓ Check VDD has 3.3V power
  ✓ Check all connections are secure

PROBLEM: Microphone shows weak signal (low amplitude)
SOLUTION:
  ✓ Speak louder or move closer to mic
  ✓ Check for loose wire connections
  ✓ Try different GPIO pins if possible

PROBLEM: No sound from speaker
SOLUTION:
  ✓ Check MAX98357A VIN has power (3.3V or 5V)
  ✓ Check SD pin is NOT grounded (leave floating)
  ✓ Check speaker is connected to + and - terminals
  ✓ Check DIN (GPIO 25) connection

PROBLEM: WiFi won't connect
SOLUTION:
  ✓ Check SSID and password in code
  ✓ Make sure router is on and in range
  ✓ Try moving ESP32 closer to router

PROBLEM: Server connection fails
SOLUTION:
  ✓ Check server IP address in code
  ✓ Make sure mic_speaker_working.py is running on server
  ✓ Check AWS security group allows port 8000


================================================================================
                            SERVER SETUP
================================================================================

Your server (mic_speaker_working.py) should be running on AWS:

  Server: 13.203.97.71
  Port: 8000
  Endpoint: POST /process

The server receives PCM audio, transcribes it, and returns TTS audio.

Make sure the server is running:
  python mic_speaker_working.py

Or with uvicorn:
  uvicorn mic_speaker_working:app --host 0.0.0.0 --port 8000


================================================================================
                              FILES
================================================================================

mic_speaker_test.ino   - Arduino test code for ESP32
README.txt             - This file (wiring and instructions)


================================================================================
                         NEXT STEPS
================================================================================

Once all tests PASS:
1. You're ready to integrate with full Microbot code
2. The same wiring works for microbot_esp32.ino
3. Just update WiFi credentials and server IP in the main code


================================================================================

