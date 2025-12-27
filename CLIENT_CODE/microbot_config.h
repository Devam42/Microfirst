/*
 * ============================================================================
 * MICROBOT ESP32 - Configuration Header
 * ============================================================================
 * 
 * Edit this file to customize your Microbot setup.
 * All hardware pins and settings in one place!
 * 
 * Based on: MICROBOT_COMPLETE_SPECIFICATION.pdf
 * ============================================================================
 */

#ifndef MICROBOT_CONFIG_H
#define MICROBOT_CONFIG_H

// ============================================================================
// WIFI CONFIGURATION
// ============================================================================

#define WIFI_SSID           "YOUR_WIFI_SSID"
#define WIFI_PASSWORD       "YOUR_WIFI_PASSWORD"

// ============================================================================
// SERVER CONFIGURATION
// ============================================================================

#define SERVER_HOST         "YOUR_SERVER_IP"   // e.g., "192.168.1.100" or cloud
#define SERVER_PORT         5000
#define PROCESS_ENDPOINT    "/process"

// ============================================================================
// AUDIO CONFIGURATION
// ============================================================================

#define SAMPLE_RATE         16000              // 16kHz sample rate
#define RECORD_TIME_MS      3000               // 3 seconds recording
#define AUDIO_BITS          16                 // 16-bit audio

// ============================================================================
// I2S MICROPHONE PINS (INMP441)
// ============================================================================
// 
// INMP441 → ESP32 Connections:
//   VDD → 3.3V
//   GND → GND
//   SD  → GPIO32 (Data)
//   SCK → GPIO27 (Bit Clock) - SHARED with speaker
//   WS  → GPIO26 (Word Select) - SHARED with speaker
//   L/R → GND (CRITICAL! Must be grounded for left channel)
//

#define I2S_MIC_SCK         27                 // Bit Clock (shared)
#define I2S_MIC_WS          26                 // Word Select (shared)
#define I2S_MIC_SD          32                 // Data input

// ============================================================================
// I2S SPEAKER AMPLIFIER PINS (MAX98357A)
// ============================================================================
//
// MAX98357A → ESP32 Connections:
//   VIN  → 3.3V
//   GND  → GND
//   DIN  → GPIO25 (Data)
//   BCLK → GPIO27 (Bit Clock) - SHARED with mic
//   LRC  → GPIO26 (Left/Right Clock) - SHARED with mic
//   GAIN → 3.3V (Maximum volume, 15dB)
//   SD   → Leave floating (amplifier enabled)
//   +/-  → Speaker terminals
//

#define I2S_SPK_BCLK        27                 // Bit Clock (shared)
#define I2S_SPK_LRC         26                 // Left/Right Clock (shared)
#define I2S_SPK_DIN         25                 // Data output

// ============================================================================
// TFT DISPLAY PINS (ILI9341 2.8" SPI)
// ============================================================================
//
// ILI9341 → ESP32 Connections:
//   VCC   → 3.3V
//   GND   → GND
//   CS    → GPIO5
//   RESET → GPIO2
//   DC    → GPIO4
//   MOSI  → GPIO23 (shared with SD)
//   SCK   → GPIO18 (shared with SD)
//   LED   → GPIO15 (backlight PWM)
//   MISO  → Not connected
//
// NOTE: Touch pins (T_*) are NOT connected
// NOTE: Built-in SD pins are NOT connected (using external SD module)
//

#define TFT_CS              5
#define TFT_RST             2
#define TFT_DC              4
#define TFT_LED             15
// TFT_MOSI = 23 (defined in TFT_eSPI User_Setup.h)
// TFT_SCK  = 18 (defined in TFT_eSPI User_Setup.h)

// ============================================================================
// SD CARD MODULE PINS (SPI)
// ============================================================================
//
// SD Card Module → ESP32 Connections:
//   VCC  → 3.3V
//   GND  → GND
//   CS   → GPIO21
//   MOSI → GPIO23 (shared with TFT)
//   MISO → GPIO19
//   SCK  → GPIO18 (shared with TFT)
//

#define SD_CS               21
#define SD_MOSI             23                 // Shared with TFT
#define SD_MISO             19
#define SD_SCK              18                 // Shared with TFT

// ============================================================================
// TOUCH SENSOR PIN (TTP223)
// ============================================================================
//
// TTP223 → ESP32 Connections:
//   VCC → 3.3V
//   GND → GND
//   SIG → GPIO33
//
// Behavior:
//   LOW when not touched
//   HIGH when touched
//

#define TOUCH_PIN           33

// ============================================================================
// POWER SYSTEM (TP4056 + 18650 Battery)
// ============================================================================
//
// TP4056 Connections:
//   IN+   → USB-C port (5V input)
//   IN-   → USB-C GND
//   B+    → Battery positive (+)
//   B-    → Battery negative (-)
//   OUT+  → Power switch input
//   OUT-  → ESP32 GND
//
// Power Switch:
//   Input  → TP4056 OUT+
//   Output → ESP32 VIN
//

// ============================================================================
// DISPLAY SETTINGS
// ============================================================================

#define TFT_ROTATION        0                  // 0=Portrait, 1=Landscape
#define TFT_BACKLIGHT_PWM   255                // 0-255 brightness

// ============================================================================
// TIMING SETTINGS
// ============================================================================

#define TOUCH_DEBOUNCE_MS   500                // Touch debounce time
#define WIFI_TIMEOUT_SEC    30                 // WiFi connection timeout
#define HTTP_TIMEOUT_MS     30000              // HTTP request timeout

// ============================================================================
// DEBUG SETTINGS
// ============================================================================

#define DEBUG_SERIAL        true               // Enable serial debug output
#define DEBUG_AUDIO         true               // Enable audio analysis output

// ============================================================================
// EXPRESSION SYSTEM (Dynamically scanned from SD card)
// ============================================================================
//
// The ESP32 automatically scans the SD card for expression videos!
// Just put your MP4 files in folders under /Expression/
//
// SD Card Structure (example):
//   /Expression/
//   ├── Burger/
//   │   ├── Burger.mp4
//   │   ├── Burger_disturb_1.mp4
//   │   ├── Burger_disturb_2.mp4
//   │   └── Burger_disturb_3.mp4
//   ├── Jungle/
//   │   ├── Jungle1.mp4
//   │   └── Jungle2.mp4
//   ├── Love/
//   │   ├── love1.mp4
//   │   ├── love2.mp4
//   │   └── love3.mp4
//   ├── Winter/
//   │   ├── winter1.mp4
//   │   └── winter2.mp4
//   └── YourNewCategory/      <-- Add your own folders!
//       └── YourVideo.mp4
//
// Supported formats: .mp4, .mjpeg, .avi
// The system will find ALL video files in ALL subfolders automatically!
//
// IMPORTANT: Expressions work WITHOUT WiFi!
// User can enjoy expressions anytime, even offline.
//

#define EXPRESSION_BASE_PATH "/Expression"
#define MAX_EXPRESSIONS 50           // Maximum expressions to store in memory
#define MAX_PATH_LENGTH 64           // Maximum path length for each expression

#endif // MICROBOT_CONFIG_H

