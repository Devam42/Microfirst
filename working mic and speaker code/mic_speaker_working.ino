#include <WiFi.h>
#include "driver/i2s.h"

// ===== PINS =====
#define I2S_MIC_SCK    27  // Shared with speaker
#define I2S_MIC_WS     26  // Shared with speaker
#define I2S_MIC_SD     32  // Mic data only

#define I2S_SPK_BCLK   27  // Shared with mic
#define I2S_SPK_LRC    26  // Shared with mic
#define I2S_SPK_DIN    25  // Speaker data only

#define BUTTON_PIN     0

// ===== WIFI CONFIG =====
const char* ssid = "Devam";
const char* password = "Devam@12";
const char* server = "13.203.97.71";
int port = 8000;

#define SAMPLE_RATE 16000
#define RECORD_TIME_MS 3000

// ===== GLOBALS =====
uint8_t* audioBuffer = nullptr;
size_t audioBufferSize = 0;

// ===== I2S MICROPHONE SETUP =====
void setupMic() {
  i2s_driver_uninstall(I2S_NUM_0);
  
  i2s_config_t cfg = {
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
  
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

// ===== I2S SPEAKER SETUP =====
void setupSpeaker() {
  i2s_driver_uninstall(I2S_NUM_0);
  
  i2s_config_t cfg = {
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
  
  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

// ===== RECORD AUDIO =====
void recordAudio() {
  Serial.println("\n🔴 RECORDING - Speak loudly for 3 seconds...");
  
  setupMic();
  
  size_t samples16Count = SAMPLE_RATE * RECORD_TIME_MS / 1000;
  audioBufferSize = samples16Count * 2;
  audioBuffer = (uint8_t*)malloc(audioBufferSize);
  
  if (!audioBuffer) {
    Serial.println("❌ Memory allocation failed!");
    return;
  }
  
  int32_t tempBuffer[128];
  int16_t* output16 = (int16_t*)audioBuffer;
  size_t samplesRecorded = 0;
  
  while (samplesRecorded < samples16Count) {
    size_t samplesToRead = min((size_t)128, samples16Count - samplesRecorded);
    size_t bytesToRead = samplesToRead * 4;
    size_t bytesRead = 0;
    
    i2s_read(I2S_NUM_0, tempBuffer, bytesToRead, &bytesRead, portMAX_DELAY);
    
    size_t samplesRead = bytesRead / 4;
    for (size_t i = 0; i < samplesRead; i++) {
      output16[samplesRecorded + i] = (int16_t)(tempBuffer[i] >> 16);
    }
    
    samplesRecorded += samplesRead;
    if (samplesRecorded % 8000 == 0) Serial.print(".");
  }
  
  Serial.println("\n⏹️ Recording complete!");
  
  // Send to server and get response
  sendToServerAndPlay();
  
  free(audioBuffer);
  audioBuffer = nullptr;
}

// ===== SEND TO SERVER AND PLAY RESPONSE =====
void sendToServerAndPlay() {
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
  client.write(audioBuffer, audioBufferSize);
  client.print(tail);
  
  Serial.println("✅ Audio sent, waiting for response...");
  
  // Skip HTTP headers
  while (client.connected()) {
    String line = client.readStringUntil('\n');
    if (line == "\r" || line.length() == 0) break;
  }
  
  // Stream response audio directly to speaker
  Serial.println("📥 Playing response...");
  setupSpeaker();
  
  uint8_t streamBuf[2048];
  size_t totalReceived = 0;
  
  while (client.connected() || client.available()) {
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
  Serial.printf("✅ Played %d bytes\n\n", totalReceived);
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
  
  Serial.println("\n🎙️ ESP32 Voice Echo (Mic + Speaker)");
  Serial.println("====================================");
  
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
  
  Serial.println("\n====================================");
  Serial.println("Press BOOT button → Speak → Hear back!");
  Serial.println("====================================\n");
}

// ===== LOOP =====
void loop() {
  checkButton();
  delay(10);
}