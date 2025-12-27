#include <WiFi.h>
#include "driver/i2s.h"

// ===== MICROPHONE PINS =====
#define I2S_MIC_SCK    27
#define I2S_MIC_WS     26
#define I2S_MIC_SD     32
#define BUTTON_PIN     0

// ===== WIFI CONFIG =====
const char* ssid = "Devam";
const char* password = "Devam@12";
const char* server = "13.203.97.71";
int port = 8000;

#define SAMPLE_RATE 16000
#define RECORD_TIME_MS 3000
#define CHUNK_SIZE 512  // Small chunks to avoid memory issues

// ===== GLOBALS =====
uint8_t* audioBuffer = nullptr;
size_t audioBufferSize = 0;

// ===== I2S MICROPHONE SETUP =====
void setupMic() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = 256,  // Smaller DMA buffers
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
  
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

// ===== RECORD AUDIO (MEMORY EFFICIENT) =====
void recordAudio() {
  Serial.println("\n🔴 RECORDING - Speak loudly for 3 seconds...");
  Serial.printf("Free heap before: %d bytes\n", ESP.getFreeHeap());
  
  setupMic();
  
  // Allocate final 16-bit buffer only (much smaller)
  size_t samples16Count = SAMPLE_RATE * RECORD_TIME_MS / 1000;
  audioBufferSize = samples16Count * 2;  // 16-bit = 2 bytes
  
  audioBuffer = (uint8_t*)malloc(audioBufferSize);
  
  if (!audioBuffer) {
    Serial.println("❌ Memory allocation failed!");
    Serial.printf("Tried to allocate: %d bytes\n", audioBufferSize);
    Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
    return;
  }
  
  Serial.printf("✅ Allocated %d bytes\n", audioBufferSize);
  
  // Small temporary buffer for reading 32-bit chunks
  int32_t tempBuffer[128];  // 128 samples = 512 bytes
  int16_t* output16 = (int16_t*)audioBuffer;
  size_t samplesRecorded = 0;
  
  // Record in small chunks and convert on-the-fly
  while (samplesRecorded < samples16Count) {
    size_t samplesToRead = min((size_t)128, samples16Count - samplesRecorded);
    size_t bytesToRead = samplesToRead * 4;  // 32-bit = 4 bytes
    size_t bytesRead = 0;
    
    // Read 32-bit chunk
    i2s_read(I2S_NUM_0, tempBuffer, bytesToRead, &bytesRead, portMAX_DELAY);
    
    // Convert 32-bit to 16-bit immediately
    size_t samplesRead = bytesRead / 4;
    for (size_t i = 0; i < samplesRead; i++) {
      output16[samplesRecorded + i] = (int16_t)(tempBuffer[i] >> 16);
    }
    
    samplesRecorded += samplesRead;
    
    // Progress indicator
    if (samplesRecorded % 8000 == 0) Serial.print(".");
  }
  
  Serial.println("\n⏹️ Recording complete!");
  Serial.printf("Recorded: %d samples (%.1f sec)\n", 
                samplesRecorded, (float)samplesRecorded / SAMPLE_RATE);
  
  // Analyze
  analyzeAudio();
  
  // Send to server
  sendToServer();
  
  // Cleanup
  free(audioBuffer);
  audioBuffer = nullptr;
  
  Serial.printf("Free heap after: %d bytes\n", ESP.getFreeHeap());
}

// ===== ANALYZE AUDIO =====
void analyzeAudio() {
  Serial.println("\n📊 Analyzing audio...");
  
  int16_t* samples = (int16_t*)audioBuffer;
  int sampleCount = audioBufferSize / 2;
  
  int nonZero = 0;
  int16_t maxVal = -32768;
  int16_t minVal = 32767;
  int32_t sum = 0;
  
  for (int i = 0; i < sampleCount; i++) {
    int16_t sample = samples[i];
    if (sample != 0) nonZero++;
    if (sample > maxVal) maxVal = sample;
    if (sample < minVal) minVal = sample;
    sum += abs(sample);
  }
  
  int16_t avgAmplitude = sum / sampleCount;
  
  Serial.printf("   Samples: %d\n", sampleCount);
  Serial.printf("   Non-zero: %d (%.1f%%)\n", nonZero, (nonZero * 100.0) / sampleCount);
  Serial.printf("   Range: %d to %d\n", minVal, maxVal);
  Serial.printf("   Avg amplitude: %d\n", avgAmplitude);
  
  if (nonZero < 1000) {
    Serial.println("   ❌ Almost all zeros - mic problem!");
  } else if (avgAmplitude < 50) {
    Serial.println("   ⚠️  Very weak signal - speak louder!");
  } else if (avgAmplitude < 200) {
    Serial.println("   ⚠️  Weak signal - try speaking closer");
  } else {
    Serial.println("   ✅ Good audio signal!");
  }
}

// ===== SEND TO SERVER =====
void sendToServer() {
  Serial.println("\n📡 Connecting to server...");
  
  WiFiClient client;
  if (!client.connect(server, port)) {
    Serial.println("❌ Connection failed!");
    return;
  }
  
  Serial.println("✅ Connected, sending audio...");
  
  String boundary = "----ESP32";
  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"audio\"; filename=\"audio.pcm\"\r\n";
  head += "Content-Type: audio/pcm\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";
  
  size_t contentLen = head.length() + audioBufferSize + tail.length();
  
  client.print("POST /process HTTP/1.1\r\n");
  client.print("Host: " + String(server) + "\r\n");
  client.print("Content-Type: multipart/form-data; boundary=" + boundary + "\r\n");
  client.print("Content-Length: " + String(contentLen) + "\r\n");
  client.print("Connection: close\r\n\r\n");
  client.print(head);
  
  // Send audio in chunks
  size_t sent = 0;
  while (sent < audioBufferSize) {
    size_t toSend = min((size_t)1024, audioBufferSize - sent);
    client.write(audioBuffer + sent, toSend);
    sent += toSend;
  }
  
  client.print(tail);
  Serial.println("✅ Audio sent!");
  
  // Read response
  Serial.println("⏳ Waiting for response...");
  
  while (client.connected()) {
    String line = client.readStringUntil('\n');
    if (line == "\r" || line.length() == 0) break;
  }
  
  String response = "";
  int bytesRead = 0;
  while (client.available() && bytesRead < 500) {
    char c = client.read();
    response += c;
    bytesRead++;
  }
  
  client.stop();
  
  Serial.println("\n📥 Server response:");
  Serial.println(response);
  Serial.println();
}

// ===== BUTTON HANDLER =====
bool lastButtonState = HIGH;

void checkButton() {
  bool reading = digitalRead(BUTTON_PIN);
  
  if (reading == LOW && lastButtonState == HIGH) {
    delay(50);
    if (digitalRead(BUTTON_PIN) == LOW) {
      recordAudio();
    }
  }
  
  lastButtonState = reading;
}

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n🎙️ ESP32 Microphone Test (INMP441)");
  Serial.println("===================================");
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ WiFi connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  
  Serial.println("\n===================================");
  Serial.println("Press BOOT button to record");
  Serial.println("Speak LOUDLY into microphone!");
  Serial.println("===================================\n");
}

// ===== LOOP =====
void loop() {
  checkButton();
  delay(10);
}