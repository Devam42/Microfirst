/*
 * SD Card Test - Minimal test to debug SD card issues
 * Upload this first to verify SD card works
 */

#include <SPI.h>
#include <SD.h>

// Try different CS pins - change this to match your wiring!
#define SD_CS   21    // Your SD CS pin

// SPI pins (standard ESP32)
#define SD_MOSI 23
#define SD_MISO 19
#define SD_SCK  18

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("\n========================================");
  Serial.println("SD Card Test for ESP32");
  Serial.println("========================================\n");
  
  Serial.println("Wiring expected:");
  Serial.printf("  CS (SS) → GPIO%d\n", SD_CS);
  Serial.printf("  MOSI    → GPIO%d\n", SD_MOSI);
  Serial.printf("  MISO    → GPIO%d\n", SD_MISO);
  Serial.printf("  SCK     → GPIO%d\n", SD_SCK);
  Serial.println("  VCC     → 3.3V");
  Serial.println("  GND     → GND\n");
  
  // Test different CS pins
  int testPins[] = {21, 4, 5, 15, 22, 13, 2, 14, 27};
  int numPins = 9;
  
  bool found = false;
  
  for (int i = 0; i < numPins; i++) {
    int csPin = testPins[i];
    
    Serial.printf("Testing GPIO%d as CS... ", csPin);
    
    // Reset SPI
    SPI.end();
    SD.end();
    delay(100);
    
    // Configure pin
    pinMode(csPin, OUTPUT);
    digitalWrite(csPin, HIGH);
    delay(50);
    
    // Try to init
    if (SD.begin(csPin)) {
      Serial.println("SUCCESS!");
      found = true;
      
      Serial.println("\n✅ SD CARD WORKING!\n");
      Serial.printf("Working CS pin: GPIO%d\n\n", csPin);
      
      // Card info
      uint8_t cardType = SD.cardType();
      Serial.print("Card Type: ");
      if (cardType == CARD_MMC) Serial.println("MMC");
      else if (cardType == CARD_SD) Serial.println("SDSC");
      else if (cardType == CARD_SDHC) Serial.println("SDHC");
      else Serial.println("UNKNOWN");
      
      uint64_t cardSize = SD.cardSize() / (1024 * 1024);
      Serial.printf("Card Size: %lluMB\n", cardSize);
      
      // List files
      Serial.println("\nFiles on SD card:");
      Serial.println("------------------");
      listDir(SD, "/", 0);
      
      break;
    } else {
      Serial.println("FAILED");
    }
    
    delay(100);
  }
  
  if (!found) {
    Serial.println("\n❌ SD CARD NOT DETECTED ON ANY PIN!\n");
    Serial.println("Troubleshooting steps:");
    Serial.println("1. Double-check all wire connections");
    Serial.println("2. Make sure SD card is inserted");
    Serial.println("3. Try a different SD card");
    Serial.println("4. Check if SD module works (LED?)");
    Serial.println("5. Some modules need 5V VCC instead of 3.3V");
    Serial.println("6. Make sure SD card is FAT32 formatted");
    
    Serial.println("\nCommon ESP32 SD Card pin mappings:");
    Serial.println("  VSPI (default): MOSI=23, MISO=19, SCK=18");
    Serial.println("  HSPI (alt):     MOSI=13, MISO=12, SCK=14");
    
    Serial.println("\nWill retry in 5 seconds...");
  }
}

void listDir(fs::FS &fs, const char *dirname, uint8_t levels) {
  File root = fs.open(dirname);
  if (!root) {
    Serial.println("Failed to open directory");
    return;
  }
  if (!root.isDirectory()) {
    Serial.println("Not a directory");
    return;
  }

  File file = root.openNextFile();
  while (file) {
    for (uint8_t i = 0; i < levels; i++) {
      Serial.print("  ");
    }
    if (file.isDirectory()) {
      Serial.print("📁 ");
      Serial.println(file.name());
      if (levels < 2) {
        listDir(fs, file.path(), levels + 1);
      }
    } else {
      Serial.print("📄 ");
      Serial.print(file.name());
      Serial.print(" (");
      Serial.print(file.size());
      Serial.println(" bytes)");
    }
    file = file.openNextFile();
  }
}

void loop() {
  // Retry every 5 seconds if failed
  delay(5000);
  
  if (SD.cardType() == CARD_NONE) {
    Serial.println("\nRetrying SD card...");
    setup();
  }
}

