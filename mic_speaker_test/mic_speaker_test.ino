/*
 * ============================================================================
 * MIC & SPEAKER TEST - HOLD TO TALK VERSION
 * ============================================================================
 * 
 * HOLD the BOOT button to record, RELEASE to process and play response!
 * 
 * Uses your existing server (mic_speaker_working.py) deployed on AWS.
 * 
 * HARDWARE CONNECTIONS:
 * 
 * INMP441 Microphone:
 *   VDD  -> 3.3V         (RED wire)
 *   GND  -> GND          (BLACK wire)
 *   SCK  -> GPIO 27      (YELLOW wire)
 *   WS   -> GPIO 26      (ORANGE wire)
 *   SD   -> GPIO 32      (BLUE wire)
 *   L/R  -> GND          (BLACK wire) ** CRITICAL! **
 * 
 * MAX98357A Speaker (FOR MAXIMUM VOLUME):
 *   VIN  -> 5V (from VIN pin or external)  (RED wire) <- USE 5V FOR LOUD!
 *   GND  -> GND          (BLACK wire)
 *   BCLK -> GPIO 27      (YELLOW wire)
 *   LRC  -> GPIO 26      (ORANGE wire)
 *   DIN  -> GPIO 25      (GREEN wire)
 *   GAIN -> 3.3V         (RED wire) <- FOR MAXIMUM 15dB GAIN
 *   SD   -> Float (don't connect)
 * 
 * FOR MAXIMUM VOLUME:
 *   - Connect MAX98357A VIN to 5V (ESP32 VIN pin or external USB 5V)
 *   - Connect GAIN to 3.3V
 *   - This gives maximum amplification without overheating ESP32's 3.3V regulator
 * 
 * ============================================================================
 */

#include <WiFi.h>
#include "driver/i2s.h"

// ============================================================================
// CONFIGURATION - Edit these for your setup
// ============================================================================

// WiFi Settings
const char* WIFI_SSID = "Devam";
const char* WIFI_PASSWORD = "Devam@12";

// Server Settings (your deployed mic_speaker_working.py on AWS)
const char* SERVER_HOST = "13.233.155.255";
const int SERVER_PORT = 5000;

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

// I2S Microphone (INMP441)
#define I2S_MIC_SCK     27
#define I2S_MIC_WS      26
#define I2S_MIC_SD      32

// I2S Speaker (MAX98357A)
#define I2S_SPK_BCLK    27
#define I2S_SPK_LRC     26
#define I2S_SPK_DIN     25

// BOOT button for HOLD-TO-TALK
#define BOOT_BUTTON     0

// ============================================================================
// AUDIO CONFIGURATION
// ============================================================================

#define SAMPLE_RATE         16000
#define MAX_RECORD_TIME_MS  5000   // Maximum 5 seconds (fits in ESP32 RAM)
#define MIN_RECORD_TIME_MS  500    // Minimum 0.5 seconds

// Buffer size: 5 seconds * 16000 samples/sec * 2 bytes = 160,000 bytes
// ESP32 has ~200KB free, so 160KB is safe

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

uint8_t* audioBuffer = nullptr;
size_t audioBufferSize = 0;
size_t audioDataSize = 0;

bool isRecording = false;
bool isProcessing = false;
unsigned long recordStartTime = 0;

// ============================================================================
// I2S MICROPHONE SETUP
// ============================================================================

void setupMicrophone() {
  // Only uninstall if already installed (ignore error if not)
  i2s_driver_uninstall(I2S_NUM_0);
  delay(50);
  
  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };
  
  i2s_driver_install(I2S_NUM_0, &config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

// ============================================================================
// I2S SPEAKER SETUP
// ============================================================================

void setupSpeaker() {
  // Only uninstall if already installed (ignore error if not)
  i2s_driver_uninstall(I2S_NUM_0);
  delay(50);
  
  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };
  
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SPK_BCLK,
    .ws_io_num = I2S_SPK_LRC,
    .data_out_num = I2S_SPK_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };
  
  i2s_driver_install(I2S_NUM_0, &config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

// ============================================================================
// START RECORDING (when button pressed)
// ============================================================================

bool startRecording() {
  Serial.println("\n🔴 RECORDING... (Release button to stop)");
  
  // Free any existing buffer first
  if (audioBuffer) {
    free(audioBuffer);
    audioBuffer = nullptr;
  }
  
  // Setup I2S for microphone FIRST
  setupMicrophone();
  
  // Calculate buffer size (5 seconds max = 160KB)
  size_t maxSamples = SAMPLE_RATE * MAX_RECORD_TIME_MS / 1000;
  audioBufferSize = maxSamples * 2;  // 16-bit = 2 bytes per sample
  audioDataSize = 0;
  
  Serial.printf("   Free heap: %d bytes\n", ESP.getFreeHeap());
  Serial.printf("   Requesting: %d bytes\n", audioBufferSize);
  
  // Try to allocate buffer
  audioBuffer = (uint8_t*)malloc(audioBufferSize);
  if (!audioBuffer) {
    // Try smaller buffer (3 seconds)
    Serial.println("   Trying smaller buffer...");
    audioBufferSize = SAMPLE_RATE * 3 * 2;  // 3 seconds = 96KB
    audioBuffer = (uint8_t*)malloc(audioBufferSize);
    
    if (!audioBuffer) {
      Serial.println("❌ Memory allocation failed!");
      Serial.printf("   Free heap: %d bytes\n", ESP.getFreeHeap());
      isRecording = false;
      return false;
    }
  }
  
  isRecording = true;
  recordStartTime = millis();
  
  Serial.printf("   Buffer allocated: %d bytes (%.1f sec max)\n", 
                audioBufferSize, (float)audioBufferSize / (SAMPLE_RATE * 2));
  return true;
}

// ============================================================================
// RECORD WHILE BUTTON HELD
// ============================================================================

bool recordWhileHolding() {
  // Check if button still pressed (BOOT button is LOW when pressed)
  if (digitalRead(BOOT_BUTTON) != LOW) {
    return false;  // Button released
  }
  
  // Check max time based on actual buffer size
  unsigned long elapsed = millis() - recordStartTime;
  size_t maxSamples = audioBufferSize / 2;  // Use actual allocated buffer
  float maxTimeMs = (float)maxSamples / SAMPLE_RATE * 1000;
  
  if (elapsed >= maxTimeMs) {
    Serial.println("\n⏱️ Buffer full - maximum time reached!");
    return false;
  }
  
  // Record samples
  size_t currentSamples = audioDataSize / 2;
  
  if (currentSamples < maxSamples) {
    int32_t tempBuffer[64];
    size_t samplesToRead = min((size_t)64, maxSamples - currentSamples);
    size_t bytesToRead = samplesToRead * 4;
    size_t bytesRead = 0;
    
    i2s_read(I2S_NUM_0, tempBuffer, bytesToRead, &bytesRead, 10 / portTICK_PERIOD_MS);
    
    if (bytesRead > 0) {
      int16_t* output = (int16_t*)audioBuffer;
      size_t samplesRead = bytesRead / 4;
      
      for (size_t i = 0; i < samplesRead; i++) {
        output[currentSamples + i] = (int16_t)(tempBuffer[i] >> 16);
      }
      audioDataSize += samplesRead * 2;
      
      // Progress indicator every 0.5 seconds
      if ((elapsed / 500) != ((elapsed - 10) / 500)) {
        Serial.printf("   Recording: %.1fs / %.1fs\n", elapsed / 1000.0, maxTimeMs / 1000.0);
      }
    }
  } else {
    return false;  // Buffer full
  }
  
  return true;  // Still recording
}

// ============================================================================
// STOP RECORDING (when button released)
// ============================================================================

void stopRecording() {
  unsigned long elapsed = millis() - recordStartTime;
  isRecording = false;
  
  Serial.printf("\n⏹️ Recording stopped! Duration: %.1fs, Size: %d bytes\n", 
                elapsed / 1000.0, audioDataSize);
  
  // Check minimum duration
  if (elapsed < MIN_RECORD_TIME_MS || audioDataSize < 1000) {
    Serial.println("⚠️ Recording too short! Hold button longer.");
    if (audioBuffer) {
      free(audioBuffer);
      audioBuffer = nullptr;
    }
    return;
  }
  
  // Analyze audio quality
  analyzeAudio();
  
  // Send to server and play response
  sendToServerAndPlay();
}

// ============================================================================
// ANALYZE RECORDED AUDIO
// ============================================================================

void analyzeAudio() {
  Serial.println("\n📊 Audio Analysis:");
  
  int16_t* samples = (int16_t*)audioBuffer;
  int sampleCount = audioDataSize / 2;
  
  int nonZero = 0;
  int16_t maxVal = -32768;
  int16_t minVal = 32767;
  int64_t sum = 0;
  
  for (int i = 0; i < sampleCount; i++) {
    int16_t sample = samples[i];
    if (sample != 0) nonZero++;
    if (sample > maxVal) maxVal = sample;
    if (sample < minVal) minVal = sample;
    sum += abs(sample);
  }
  
  int avgAmplitude = sum / sampleCount;
  float nonZeroPercent = (nonZero * 100.0) / sampleCount;
  
  Serial.printf("   Samples: %d\n", sampleCount);
  Serial.printf("   Non-zero: %.1f%%\n", nonZeroPercent);
  Serial.printf("   Range: %d to %d\n", minVal, maxVal);
  Serial.printf("   Avg amplitude: %d\n", avgAmplitude);
  
  if (nonZeroPercent < 5) {
    Serial.println("   ⚠️ WARNING: Mostly silence - check mic wiring!");
  } else if (avgAmplitude < 100) {
    Serial.println("   ⚠️ WARNING: Weak signal - speak louder!");
  } else {
    Serial.println("   ✅ Good audio signal!");
  }
}

// ============================================================================
// SEND TO SERVER AND PLAY RESPONSE
// ============================================================================

void sendToServerAndPlay() {
  Serial.println("\n📡 Connecting to server...");
  isProcessing = true;
  
  WiFiClient client;
  if (!client.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("❌ Connection failed!");
    Serial.printf("   Server: %s:%d\n", SERVER_HOST, SERVER_PORT);
    if (audioBuffer) {
      free(audioBuffer);
      audioBuffer = nullptr;
    }
    isProcessing = false;
    return;
  }
  
  Serial.println("✅ Connected! Sending audio...");
  
  // Build multipart request
  String boundary = "----ESP32Microbot";
  String header = "--" + boundary + "\r\n";
  header += "Content-Disposition: form-data; name=\"audio\"; filename=\"audio.pcm\"\r\n";
  header += "Content-Type: audio/pcm\r\n\r\n";
  String footer = "\r\n--" + boundary + "--\r\n";
  
  size_t contentLength = header.length() + audioDataSize + footer.length();
  
  // Send HTTP request
  client.print("POST /process HTTP/1.1\r\n");
  client.print("Host: ");
  client.print(SERVER_HOST);
  client.print("\r\n");
  client.print("Content-Type: multipart/form-data; boundary=");
  client.print(boundary);
  client.print("\r\n");
  client.print("Content-Length: ");
  client.print(contentLength);
  client.print("\r\n");
  client.print("Connection: close\r\n\r\n");
  client.print(header);
  
  // Send audio in chunks
  size_t sent = 0;
  while (sent < audioDataSize) {
    size_t chunk = min((size_t)1024, audioDataSize - sent);
    client.write(audioBuffer + sent, chunk);
    sent += chunk;
  }
  
  client.print(footer);
  Serial.printf("✅ Sent %d bytes!\n", audioDataSize);
  
  // Free recording buffer
  free(audioBuffer);
  audioBuffer = nullptr;
  
  // Wait for response
  Serial.println("\n⏳ Waiting for server response...");
  
  // Skip HTTP headers
  unsigned long timeout = millis() + 30000;
  while (client.connected() && millis() < timeout) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      if (line == "\r" || line.length() == 0) break;
    }
  }
  
  // Play response audio
  Serial.println("\n🔊 Playing response...");
  setupSpeaker();
  
  uint8_t streamBuf[2048];
  size_t totalReceived = 0;
  
  while ((client.connected() || client.available()) && millis() < timeout) {
    if (client.available()) {
      int len = client.read(streamBuf, sizeof(streamBuf));
      if (len > 0) {
        totalReceived += len;
        size_t written;
        i2s_write(I2S_NUM_0, streamBuf, len, &written, portMAX_DELAY);
      }
    }
  }
  
  client.stop();
  isProcessing = false;
  
  if (totalReceived > 0) {
    Serial.printf("\n✅ SUCCESS! Played %d bytes of audio\n", totalReceived);
  } else {
    Serial.println("\n❌ No audio received from server!");
    Serial.println("   Check: Is mic_speaker_working.py running?");
  }
  
  Serial.println("\n────────────────────────────────────────");
  Serial.println("🎤 Ready! HOLD BOOT button to speak again");
  Serial.println("────────────────────────────────────────");
}

// ============================================================================
// PLAY TEST TONE (for speaker test)
// ============================================================================

void playTestTone() {
  Serial.println("\n🔊 Playing test tone (440Hz for 1 second)...");
  
  setupSpeaker();
  
  const int duration_ms = 1000;
  const float frequency = 440.0;
  const int numSamples = SAMPLE_RATE * duration_ms / 1000;
  const float amplitude = 20000;  // Loud!
  
  int16_t* toneBuffer = (int16_t*)malloc(numSamples * 2);
  if (!toneBuffer) {
    Serial.println("❌ Could not allocate buffer!");
    return;
  }
  
  // Generate sine wave
  for (int i = 0; i < numSamples; i++) {
    float t = (float)i / SAMPLE_RATE;
    toneBuffer[i] = (int16_t)(amplitude * sin(2 * PI * frequency * t));
  }
  
  // Play
  size_t bytesWritten;
  i2s_write(I2S_NUM_0, toneBuffer, numSamples * 2, &bytesWritten, portMAX_DELAY);
  
  delay(100);
  i2s_zero_dma_buffer(I2S_NUM_0);
  free(toneBuffer);
  
  Serial.println("✅ Done! Did you hear a beep?");
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("\n");
  Serial.println("╔════════════════════════════════════════════════════════╗");
  Serial.println("║    MIC & SPEAKER TEST - HOLD TO TALK                   ║");
  Serial.println("╚════════════════════════════════════════════════════════╝");
  Serial.println();
  
  // Show wiring info
  Serial.println("WIRING (for MAXIMUM VOLUME):");
  Serial.println("─────────────────────────────────────────────────────────");
  Serial.println("INMP441:  VDD→3.3V, GND→GND, SCK→27, WS→26, SD→32, L/R→GND");
  Serial.println("MAX98357A: VIN→5V(!), GND→GND, BCLK→27, LRC→26, DIN→25");
  Serial.println("           GAIN→3.3V (for max volume)");
  Serial.println("─────────────────────────────────────────────────────────");
  Serial.println();
  Serial.println("💡 TIP: For maximum volume without ESP32 overheating:");
  Serial.println("   Connect MAX98357A VIN to 5V (ESP32 VIN pin or external)");
  Serial.println("   Then you can safely connect GAIN to 3.3V");
  Serial.println();
  
  // Setup BOOT button
  pinMode(BOOT_BUTTON, INPUT_PULLUP);
  
  // Connect WiFi
  Serial.printf("📡 Connecting to WiFi: %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.printf("✅ WiFi connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println();
    Serial.println("❌ WiFi failed! Check credentials.");
  }
  
  Serial.println();
  Serial.println("════════════════════════════════════════════════════════");
  Serial.println("  🎤 HOLD the BOOT button and SPEAK");
  Serial.println("  🔊 RELEASE to hear the response from server");
  Serial.println("════════════════════════════════════════════════════════");
  Serial.println();
  Serial.println("Serial commands:");
  Serial.println("  't' = Play test tone (speaker test)");
  Serial.println("  'w' = Reconnect WiFi");
  Serial.println();
}

// ============================================================================
// LOOP
// ============================================================================

void loop() {
  // Handle serial commands
  if (Serial.available()) {
    char cmd = Serial.read();
    
    switch (cmd) {
      case 't':
      case 'T':
        playTestTone();
        break;
      case 'w':
      case 'W':
        Serial.println("Reconnecting WiFi...");
        WiFi.disconnect();
        delay(500);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        while (WiFi.status() != WL_CONNECTED) {
          delay(500);
          Serial.print(".");
        }
        Serial.printf("\n✅ Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        break;
    }
  }
  
  // Don't process button if already recording or processing
  if (isProcessing) {
    delay(10);
    return;
  }
  
  // Read button state (LOW when pressed)
  static bool wasPressed = false;
  bool buttonPressed = (digitalRead(BOOT_BUTTON) == LOW);
  
  // Button state machine
  if (buttonPressed && !wasPressed && !isRecording) {
    // Button just pressed - start recording
    delay(50);  // Debounce
    if (digitalRead(BOOT_BUTTON) == LOW) {
      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("❌ WiFi not connected! Press 'w' to reconnect.");
      } else {
        if (startRecording()) {
          wasPressed = true;
        }
      }
    }
  }
  else if (isRecording) {
    // Currently recording
    if (!recordWhileHolding()) {
      // Button released or max time reached
      stopRecording();
      wasPressed = false;
    }
  }
  else if (!buttonPressed) {
    wasPressed = false;
  }
  
  delay(5);  // Small delay for stability
}
