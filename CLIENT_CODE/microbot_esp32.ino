/*
 * ============================================================================
 * MICROBOT ESP32 - Complete Voice-Activated Robot with Video Expressions
 * ============================================================================
 * 
 * Hardware:
 * - ESP32-WROOM-32 DevKit
 * - INMP441 I2S Microphone
 * - MAX98357A I2S Amplifier + Speaker
 * - ILI9341 2.8" TFT Display (SPI) - 240x320
 * - MicroSD Card Module (SPI)
 * - TTP223 Touch Sensor
 * 
 * Flow (HOLD TO SPEAK):
 * 1. User HOLDS touch sensor → Recording starts
 * 2. User RELEASES touch sensor → Recording stops
 * 3. ESP32 sends PCM audio to server via WiFi
 * 4. Server: STT → AI → TTS → returns PCM audio
 * 5. MAX98357A plays response audio (I2S TX)
 * 6. TFT plays RGB565 video expressions from SD card
 * 
 * EXPRESSION SYSTEM:
 * - Expressions stored as RGB565 .bin files on SD card
 * - Converted from MP4 using convert_mp4_to_rgb565.py
 * - Played as smooth video animations on TFT
 * 
 * ============================================================================
 */

#include <WiFi.h>
#include "driver/i2s.h"
#include <SD.h>
#include <SPI.h>
#include <TFT_eSPI.h>

// ============================================================================
// CONFIGURATION - Edit these values for your setup
// ============================================================================

// WiFi Configuration
const char* WIFI_SSID = "Devam";
const char* WIFI_PASSWORD = "Devam@12";

// Server Configuration
const char* SERVER_HOST = "13.233.155.255";
const int SERVER_PORT = 5000;

// Audio Configuration
#define SAMPLE_RATE 16000
#define MAX_RECORD_TIME_MS 10000
#define MIN_RECORD_TIME_MS 500

// Expression Configuration
#define EXPR_WIDTH 240
#define EXPR_HEIGHT 320
#define EXPR_FPS 15
#define EXPR_CHUNK_LINES 16  // Lines to read at a time (balance between speed and RAM)
#define EXPR_CHUNK_SIZE (EXPR_WIDTH * EXPR_CHUNK_LINES * 2)  // 7680 bytes per chunk

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

// I2S Microphone (INMP441)
#define I2S_MIC_SCK     27
#define I2S_MIC_WS      26
#define I2S_MIC_SD      32

// I2S Speaker Amplifier (MAX98357A)
#define I2S_SPK_BCLK    27
#define I2S_SPK_LRC     26
#define I2S_SPK_DIN     25

// TFT Display (ILI9341 SPI) - Pins in User_Setup.h
#define TFT_CS          5
#define TFT_RST         2
#define TFT_DC          4
#define TFT_LED         15

// SD Card (SPI)
#define SD_CS           21
#define SD_MOSI         23
#define SD_MISO         19
#define SD_SCK          18

// Touch Sensor (TTP223)
#define TOUCH_PIN       33

// ============================================================================
// GLOBAL VARIABLES
// ============================================================================

TFT_eSPI tft = TFT_eSPI();

// Audio buffers
uint8_t* audioBuffer = nullptr;
size_t audioBufferSize = 0;
size_t audioDataSize = 0;

// State
bool isRecording = false;
bool isPlaying = false;
bool isPlayingExpression = false;
bool isTouching = false;
String lastTranscription = "";
String lastResponse = "";

// Touch handling
unsigned long touchStartTime = 0;

// Expression system
#define MAX_EXPRESSIONS 50
#define MAX_PATH_LENGTH 64
#define EXPRESSION_BASE_PATH "/Expression"

char expressionPaths[MAX_EXPRESSIONS][MAX_PATH_LENGTH];
int numExpressions = 0;
bool expressionsLoaded = false;
int currentExpressionIndex = -1;

// Expression playback
File exprFile;
int exprTotalFrames = 0;
int exprCurrentFrame = 0;
int exprFps = EXPR_FPS;
bool exprLoop = true;
unsigned long lastFrameTime = 0;
unsigned long lastIdleExprTime = 0;
const unsigned long IDLE_EXPRESSION_INTERVAL = 30000;

// Chunk buffer for expression playback
uint8_t exprChunkBuffer[EXPR_CHUNK_SIZE];

// ============================================================================
// I2S MICROPHONE SETUP
// ============================================================================

void setupMicrophone() {
  i2s_driver_uninstall(I2S_NUM_0);
  
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
  i2s_driver_uninstall(I2S_NUM_0);
  
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
// EXPRESSION SYSTEM - RGB565 Video Playback
// ============================================================================

void scanExpressionsFolder(File dir, String parentPath) {
  while (true) {
    File entry = dir.openNextFile();
    if (!entry) break;
    
    String entryName = entry.name();
    String fullPath = parentPath + "/" + entryName;
    
    if (entry.isDirectory()) {
      scanExpressionsFolder(entry, fullPath);
    } else {
      String lowerName = entryName;
      lowerName.toLowerCase();
      
      // Look for .bin files (RGB565 format)
      if (lowerName.endsWith(".bin")) {
        if (numExpressions < MAX_EXPRESSIONS) {
          strncpy(expressionPaths[numExpressions], fullPath.c_str(), MAX_PATH_LENGTH - 1);
          expressionPaths[numExpressions][MAX_PATH_LENGTH - 1] = '\0';
          Serial.printf("   🎬 %s\n", expressionPaths[numExpressions]);
          numExpressions++;
        }
      }
    }
    entry.close();
  }
}

void loadExpressionsFromSD() {
  Serial.println("\n📂 Scanning for RGB565 expressions...");
  numExpressions = 0;
  expressionsLoaded = false;
  
  File expressionDir = SD.open(EXPRESSION_BASE_PATH);
  if (!expressionDir || !expressionDir.isDirectory()) {
    Serial.println("❌ /Expression folder not found!");
    return;
  }
  
  scanExpressionsFolder(expressionDir, EXPRESSION_BASE_PATH);
  expressionDir.close();
  
  if (numExpressions > 0) {
    expressionsLoaded = true;
    Serial.printf("✅ Found %d expression videos!\n", numExpressions);
  } else {
    Serial.println("⚠️ No .bin expression files found!");
  }
}

bool loadExpressionManifest(const char* binPath) {
  // Default values
  exprFps = EXPR_FPS;
  exprTotalFrames = 0;
  exprLoop = true;
  
  // Construct manifest path
  String manifestPath = String(binPath);
  manifestPath.replace(".bin", "_manifest.txt");
  
  File mf = SD.open(manifestPath.c_str());
  if (!mf) {
    // Estimate frames from file size
    File binFile = SD.open(binPath);
    if (binFile) {
      long fileSize = binFile.size();
      long frameSize = EXPR_WIDTH * EXPR_HEIGHT * 2;
      exprTotalFrames = fileSize / frameSize;
      binFile.close();
    }
    return true;
  }
  
  while (mf.available()) {
    String line = mf.readStringUntil('\n');
    line.trim();
    if (line.length() == 0 || line.startsWith("#")) continue;
    
    int eq = line.indexOf('=');
    if (eq < 0) continue;
    
    String key = line.substring(0, eq);
    String val = line.substring(eq + 1);
    key.trim();
    val.trim();
    
    if (key == "fps") exprFps = val.toInt();
    else if (key == "frames") exprTotalFrames = val.toInt();
    else if (key == "loop") exprLoop = (val.toInt() != 0);
  }
  mf.close();
  
  return true;
}

bool startExpression(const char* binPath) {
  stopExpression();
  
  Serial.printf("🎬 Starting: %s\n", binPath);
  
  loadExpressionManifest(binPath);
  
  exprFile = SD.open(binPath);
  if (!exprFile) {
    Serial.printf("❌ Could not open: %s\n", binPath);
    return false;
  }
  
  exprCurrentFrame = 0;
  isPlayingExpression = true;
  lastFrameTime = millis();
  
  Serial.printf("   Frames: %d, FPS: %d\n", exprTotalFrames, exprFps);
  
  return true;
}

void stopExpression() {
  if (exprFile) {
    exprFile.close();
  }
  isPlayingExpression = false;
  exprCurrentFrame = 0;
}

bool playExpressionFrame() {
  if (!exprFile || !isPlayingExpression) return false;
  
  // Check if finished
  if (exprTotalFrames > 0 && exprCurrentFrame >= exprTotalFrames) {
    if (exprLoop) {
      exprFile.seek(0);
      exprCurrentFrame = 0;
    } else {
      stopExpression();
      return false;
    }
  }
  
  // Check by file position
  if (exprFile.position() >= exprFile.size()) {
    if (exprLoop) {
      exprFile.seek(0);
      exprCurrentFrame = 0;
    } else {
      stopExpression();
      return false;
    }
  }
  
  // Read and display frame in chunks
  for (int y = 0; y < EXPR_HEIGHT; y += EXPR_CHUNK_LINES) {
    int linesToRead = min(EXPR_CHUNK_LINES, EXPR_HEIGHT - y);
    int bytesToRead = EXPR_WIDTH * linesToRead * 2;
    
    int bytesRead = exprFile.read(exprChunkBuffer, bytesToRead);
    if (bytesRead != bytesToRead) {
      Serial.printf("⚠️ Read error at frame %d\n", exprCurrentFrame);
      stopExpression();
      return false;
    }
    
    // Push directly to TFT
    tft.pushImage(0, y, EXPR_WIDTH, linesToRead, (uint16_t*)exprChunkBuffer);
  }
  
  exprCurrentFrame++;
  return true;
}

void playRandomExpression() {
  if (!expressionsLoaded || numExpressions == 0) return;
  
  int index = random(0, numExpressions);
  currentExpressionIndex = index;
  startExpression(expressionPaths[index]);
}

void updateExpression() {
  if (!isPlayingExpression) return;
  
  unsigned long now = millis();
  unsigned long frameInterval = 1000 / exprFps;
  
  if (now - lastFrameTime >= frameInterval) {
    lastFrameTime = now;
    playExpressionFrame();
  }
}

// ============================================================================
// RECORDING FUNCTIONS
// ============================================================================

bool startRecording() {
  Serial.println("\n🔴 RECORDING...");
  
  isRecording = true;
  touchStartTime = millis();
  
  // Stop expression while recording
  stopExpression();
  
  // Show recording indicator
  tft.fillScreen(TFT_BLACK);
  tft.fillCircle(tft.width()/2, 80, 40, TFT_RED);
  tft.setTextColor(TFT_WHITE);
  tft.setTextSize(2);
  tft.setCursor(60, 150);
  tft.println("Recording...");
  tft.setTextSize(1);
  tft.setCursor(50, 180);
  tft.println("Release when done");
  
  setupMicrophone();
  
  size_t maxSamples = SAMPLE_RATE * MAX_RECORD_TIME_MS / 1000;
  audioBufferSize = maxSamples * 2;
  audioDataSize = 0;
  
  audioBuffer = (uint8_t*)malloc(audioBufferSize);
  if (!audioBuffer) {
    Serial.println("❌ Memory allocation failed!");
    isRecording = false;
    return false;
  }
  
  return true;
}

bool recordWhileHolding() {
  if (digitalRead(TOUCH_PIN) != HIGH) {
    return false;  // Touch released
  }
  
  unsigned long elapsed = millis() - touchStartTime;
  if (elapsed >= MAX_RECORD_TIME_MS) {
    Serial.println("\n⏱️ Max time reached!");
    return false;
  }
  
  size_t maxSamples = SAMPLE_RATE * MAX_RECORD_TIME_MS / 1000;
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
      
      // Update recording progress
      if ((elapsed / 500) != ((elapsed - 10) / 500)) {
        tft.fillRect(50, 200, 140, 20, TFT_BLACK);
        tft.setCursor(50, 200);
        tft.setTextColor(TFT_RED);
        tft.printf("%.1fs / %.1fs", elapsed/1000.0, MAX_RECORD_TIME_MS/1000.0);
      }
    }
  }
  
  return true;
}

void stopRecording() {
  unsigned long elapsed = millis() - touchStartTime;
  Serial.printf("\n⏹️ Recording stopped! %.1fs, %d bytes\n", elapsed/1000.0, audioDataSize);
  
  isRecording = false;
  
  if (elapsed < MIN_RECORD_TIME_MS || audioDataSize < 1000) {
    Serial.println("⚠️ Too short!");
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_YELLOW);
    tft.setTextSize(2);
    tft.setCursor(40, 100);
    tft.println("Too short!");
    if (audioBuffer) {
      free(audioBuffer);
      audioBuffer = nullptr;
    }
    delay(1000);
    playRandomExpression();
    return;
  }
  
  // Show processing
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_YELLOW);
  tft.setTextSize(2);
  tft.setCursor(40, 100);
  tft.println("Processing...");
  
  sendAndReceive();
}

// ============================================================================
// SERVER COMMUNICATION
// ============================================================================

void sendAndReceive() {
  Serial.println("\n📡 Connecting to server...");
  
  WiFiClient client;
  if (!client.connect(SERVER_HOST, SERVER_PORT)) {
    Serial.println("❌ Connection failed!");
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_RED);
    tft.setTextSize(2);
    tft.setCursor(20, 100);
    tft.println("Server error!");
    if (audioBuffer) {
      free(audioBuffer);
      audioBuffer = nullptr;
    }
    delay(2000);
    playRandomExpression();
    return;
  }
  
  Serial.println("✅ Connected, sending audio...");
  
  // Build multipart request
  String boundary = "----ESP32Microbot";
  String header = "--" + boundary + "\r\n";
  header += "Content-Disposition: form-data; name=\"audio\"; filename=\"audio.pcm\"\r\n";
  header += "Content-Type: audio/pcm\r\n\r\n";
  String footer = "\r\n--" + boundary + "--\r\n";
  
  size_t contentLength = header.length() + audioDataSize + footer.length();
  
  client.print("POST /process HTTP/1.1\r\n");
  client.print("Host: " + String(SERVER_HOST) + "\r\n");
  client.print("Content-Type: multipart/form-data; boundary=" + boundary + "\r\n");
  client.print("Content-Length: " + String(contentLength) + "\r\n");
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
  
  free(audioBuffer);
  audioBuffer = nullptr;
  
  // Read response headers
  Serial.println("⏳ Waiting for response...");
  
  String transcription = "";
  String responseText = "";
  int contentLength2 = 0;
  
  unsigned long timeout = millis() + 30000;
  
  while (client.connected() && millis() < timeout) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      
      if (line.startsWith("X-Transcription:")) {
        transcription = line.substring(17);
        transcription.trim();
      } else if (line.startsWith("X-Response-Text:")) {
        responseText = line.substring(17);
        responseText.trim();
      } else if (line.startsWith("Content-Length:")) {
        contentLength2 = line.substring(16).toInt();
      }
      
      if (line == "\r" || line.length() == 0) break;
    }
  }
  
  lastTranscription = transcription;
  lastResponse = responseText;
  
  Serial.printf("🎤 You: \"%s\"\n", transcription.c_str());
  Serial.printf("🤖 Bot: \"%s\"\n", responseText.c_str());
  
  // Start playing expression while receiving audio
  playRandomExpression();
  
  // Stream response audio to speaker
  if (contentLength2 > 0) {
    Serial.printf("📥 Playing %d bytes audio...\n", contentLength2);
    
    setupSpeaker();
    isPlaying = true;
    
    uint8_t buffer[2048];
    size_t totalReceived = 0;
    
    while ((client.connected() || client.available()) && millis() < timeout) {
      // Update expression while playing audio
      updateExpression();
      
      if (client.available()) {
        int len = client.read(buffer, sizeof(buffer));
        if (len > 0) {
          totalReceived += len;
          size_t written;
          i2s_write(I2S_NUM_0, buffer, len, &written, portMAX_DELAY);
        }
      }
    }
    
    isPlaying = false;
    Serial.printf("✅ Played %d bytes\n", totalReceived);
  }
  
  client.stop();
  lastIdleExprTime = millis();
}

// ============================================================================
// DISPLAY FUNCTIONS
// ============================================================================

void displayIdleScreen() {
  tft.fillScreen(TFT_BLACK);
  
  tft.drawRect(5, 5, tft.width() - 10, tft.height() - 10, TFT_CYAN);
  
  tft.setTextColor(TFT_CYAN);
  tft.setTextSize(3);
  tft.setCursor(45, 40);
  tft.println("MICROBOT");
  
  // Robot face
  int cx = tft.width() / 2;
  int cy = 130;
  tft.drawRoundRect(cx - 45, cy - 35, 90, 70, 12, TFT_CYAN);
  tft.fillCircle(cx - 18, cy - 5, 10, TFT_CYAN);
  tft.fillCircle(cx + 18, cy - 5, 10, TFT_CYAN);
  tft.fillCircle(cx - 18, cy - 5, 5, TFT_BLACK);
  tft.fillCircle(cx + 18, cy - 5, 5, TFT_BLACK);
  tft.drawLine(cx - 18, cy + 18, cx + 18, cy + 18, TFT_CYAN);
  tft.drawLine(cx, cy - 35, cx, cy - 50, TFT_CYAN);
  tft.fillCircle(cx, cy - 55, 6, TFT_YELLOW);
  
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE);
  tft.setCursor(40, 200);
  tft.println("HOLD to talk");
  
  tft.setTextSize(1);
  tft.setTextColor(TFT_DARKGREY);
  tft.setCursor(50, 230);
  tft.println("Release when done");
  
  if (expressionsLoaded) {
    tft.setTextColor(TFT_GREEN);
    tft.setCursor(60, 260);
    tft.printf("%d expressions", numExpressions);
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    tft.setTextColor(TFT_GREEN);
    tft.setCursor(10, 290);
    tft.print("WiFi: ");
    tft.print(WiFi.localIP());
  }
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n============================================");
  Serial.println("🤖 MICROBOT ESP32 - Video Expression Robot");
  Serial.println("============================================");
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
  
  // Touch sensor
  pinMode(TOUCH_PIN, INPUT);
  Serial.printf("✅ Touch sensor (GPIO%d)\n", TOUCH_PIN);
  
  // TFT backlight
  pinMode(TFT_LED, OUTPUT);
  digitalWrite(TFT_LED, HIGH);
  
  // CS pins
  pinMode(TFT_CS, OUTPUT);
  digitalWrite(TFT_CS, HIGH);
  pinMode(SD_CS, OUTPUT);
  digitalWrite(SD_CS, HIGH);
  
  // Initialize SD card FIRST (before TFT to avoid SPI conflicts)
  Serial.println("\n💾 Initializing SD card...");
  
  // Initialize SPI for SD card
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  delay(100);
  
  bool sdOK = false;
  
  // Try multiple speeds for compatibility
  if (SD.begin(SD_CS, SPI, 4000000)) {
    sdOK = true;
    Serial.println("✅ SD card OK (4MHz)");
  } else {
    Serial.println("   4MHz failed, trying 1MHz...");
    SD.end();
    delay(50);
    if (SD.begin(SD_CS, SPI, 1000000)) {
      sdOK = true;
      Serial.println("✅ SD card OK (1MHz)");
    } else {
      Serial.println("   1MHz failed, trying 400kHz...");
      SD.end();
      delay(50);
      if (SD.begin(SD_CS, SPI, 400000)) {
        sdOK = true;
        Serial.println("✅ SD card OK (400kHz)");
      }
    }
  }
  
  if (sdOK) {
    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    Serial.printf("   Card size: %llu MB\n", cardSize);
    loadExpressionsFromSD();
  } else {
    Serial.println("❌ SD card failed!");
    Serial.println("   Check: SD inserted? FAT32 format?");
  }
  
  // Initialize TFT
  Serial.println("\n📺 Initializing TFT...");
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);
  Serial.println("✅ TFT ready");
  
  // Show startup
  tft.setTextColor(TFT_CYAN);
  tft.setTextSize(2);
  tft.setCursor(20, 50);
  tft.println("MICROBOT");
  tft.setTextSize(1);
  tft.setCursor(20, 80);
  tft.println("Initializing...");
  
  // Connect WiFi
  tft.setCursor(20, 100);
  tft.println("Connecting WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("📡 WiFi");
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n✅ WiFi: %s\n", WiFi.localIP().toString().c_str());
    tft.setTextColor(TFT_GREEN);
    tft.setCursor(20, 120);
    tft.println("WiFi connected!");
  } else {
    Serial.println("\n⚠️ WiFi failed!");
    tft.setTextColor(TFT_YELLOW);
    tft.setCursor(20, 120);
    tft.println("WiFi offline");
  }
  
  delay(1500);
  
  // Start with random expression or idle screen
  if (expressionsLoaded && numExpressions > 0) {
    playRandomExpression();
  } else {
    displayIdleScreen();
  }
  
  lastIdleExprTime = millis();
  
  Serial.println("\n============================================");
  Serial.println("🎤 Ready! HOLD touch sensor to speak");
  Serial.printf("   Server: %s:%d\n", SERVER_HOST, SERVER_PORT);
  Serial.println("============================================\n");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  bool touchState = (digitalRead(TOUCH_PIN) == HIGH);
  
  // Touch state changes
  if (touchState && !isTouching && !isPlaying) {
    isTouching = true;
    Serial.println("\n👆 Touch - starting recording...");
    
    if (WiFi.status() == WL_CONNECTED) {
      startRecording();
    } else {
      Serial.println("📡 No WiFi - playing expression");
      playRandomExpression();
      isTouching = false;
    }
  }
  else if (!touchState && isTouching) {
    isTouching = false;
    if (isRecording) {
      Serial.println("\n👆 Released - stopping recording...");
      stopRecording();
    }
  }
  else if (isTouching && isRecording) {
    if (!recordWhileHolding()) {
      isTouching = false;
      stopRecording();
    }
  }
  
  // Update expression animation
  if (!isRecording) {
    updateExpression();
  }
  
  // Check for idle expression change
  if (!isTouching && !isRecording && !isPlaying) {
    unsigned long now = millis();
    
    // If not playing expression and idle for a while, start one
    if (!isPlayingExpression && expressionsLoaded && numExpressions > 0) {
      if (now - lastIdleExprTime > IDLE_EXPRESSION_INTERVAL) {
        playRandomExpression();
        lastIdleExprTime = now;
      }
    }
    
    // If expression finished playing, show idle screen briefly then play another
    if (!isPlayingExpression && expressionsLoaded) {
      delay(2000);
      playRandomExpression();
    }
  }
  
  delay(1);
}
