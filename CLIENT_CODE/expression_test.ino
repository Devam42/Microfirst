/*
 * Expression Playback Test
 * =========================
 * Tests playing RGB565 binary animations on TFT
 * 
 * Before running:
 * 1. Run the convert_mp4_to_rgb565.py script to convert your MP4s
 * 2. Copy the converted files to SD card /Expression folder
 * 
 * Expected SD card structure:
 *   /Expression/
 *   ├── Burger/
 *   │   ├── Burger.bin
 *   │   └── Burger_manifest.txt
 *   ├── Love/
 *   │   ├── love1.bin
 *   │   └── love1_manifest.txt
 *   └── ...
 */

#include <SPI.h>
#include <SD.h>
#include <TFT_eSPI.h>
#include "expression_player.h"

// Pin definitions
#define SD_CS       21
#define TFT_LED     15
#define TOUCH_PIN   33

// Display
TFT_eSPI tft = TFT_eSPI();

// Expression player
ExpressionPlayer* player = nullptr;

// Expression files found
#define MAX_EXPRESSIONS 50
char expressionPaths[MAX_EXPRESSIONS][64];
int numExpressions = 0;
int currentExpressionIndex = 0;

// Timing
unsigned long lastFrameTime = 0;
unsigned long lastTouchTime = 0;

// Scan for .bin files in Expression folder
void scanExpressions() {
    Serial.println("\n📂 Scanning for expressions...");
    numExpressions = 0;
    
    File root = SD.open("/Expression");
    if (!root) {
        Serial.println("❌ Could not open /Expression folder!");
        return;
    }
    
    scanFolder(root, "/Expression");
    root.close();
    
    if (numExpressions > 0) {
        Serial.printf("✅ Found %d expression files!\n\n", numExpressions);
    } else {
        Serial.println("⚠️ No .bin expression files found!");
        Serial.println("   Run convert_mp4_to_rgb565.py first!");
    }
}

void scanFolder(File dir, String path) {
    while (true) {
        File entry = dir.openNextFile();
        if (!entry) break;
        
        String entryName = entry.name();
        String fullPath = path + "/" + entryName;
        
        if (entry.isDirectory()) {
            scanFolder(entry, fullPath);
        } else {
            String lowerName = entryName;
            lowerName.toLowerCase();
            
            if (lowerName.endsWith(".bin")) {
                if (numExpressions < MAX_EXPRESSIONS) {
                    strncpy(expressionPaths[numExpressions], fullPath.c_str(), 63);
                    expressionPaths[numExpressions][63] = '\0';
                    Serial.printf("   🎬 %s\n", expressionPaths[numExpressions]);
                    numExpressions++;
                }
            }
        }
        entry.close();
    }
}

void playExpression(int index) {
    if (index < 0 || index >= numExpressions) return;
    
    Serial.printf("\n▶️ Playing expression %d: %s\n", index, expressionPaths[index]);
    
    if (player->load(expressionPaths[index])) {
        currentExpressionIndex = index;
        lastFrameTime = millis();
    } else {
        // Show error on display
        tft.fillScreen(TFT_BLACK);
        tft.setTextColor(TFT_RED);
        tft.setTextSize(2);
        tft.setCursor(10, 100);
        tft.println("Load Error!");
        tft.setTextSize(1);
        tft.setCursor(10, 130);
        tft.println(expressionPaths[index]);
    }
}

void nextExpression() {
    if (numExpressions == 0) return;
    
    int next = (currentExpressionIndex + 1) % numExpressions;
    playExpression(next);
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n============================================");
    Serial.println("Expression Playback Test");
    Serial.println("============================================\n");
    
    // Touch sensor
    pinMode(TOUCH_PIN, INPUT);
    
    // TFT backlight
    pinMode(TFT_LED, OUTPUT);
    digitalWrite(TFT_LED, HIGH);
    
    // Initialize TFT
    Serial.println("📺 Initializing TFT...");
    tft.init();
    tft.setRotation(0);  // Portrait
    tft.fillScreen(TFT_BLACK);
    
    tft.setTextColor(TFT_CYAN);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.println("Expression Test");
    tft.setTextSize(1);
    tft.setCursor(10, 40);
    tft.println("Initializing...");
    
    Serial.println("✅ TFT ready");
    
    // Initialize SD card
    Serial.println("\n💾 Initializing SD card...");
    tft.setCursor(10, 55);
    tft.println("SD card...");
    
    pinMode(SD_CS, OUTPUT);
    digitalWrite(SD_CS, HIGH);
    
    SPI.begin(18, 19, 23, SD_CS);
    
    if (!SD.begin(SD_CS, SPI, 4000000)) {
        Serial.println("❌ SD card failed!");
        tft.setTextColor(TFT_RED);
        tft.setCursor(10, 70);
        tft.println("SD FAILED!");
        while(1) delay(100);
    }
    
    Serial.println("✅ SD card ready");
    tft.setTextColor(TFT_GREEN);
    tft.setCursor(10, 70);
    tft.println("SD OK!");
    
    // Create player
    player = new ExpressionPlayer(&tft);
    
    // Scan for expressions
    tft.setTextColor(TFT_WHITE);
    tft.setCursor(10, 85);
    tft.println("Scanning...");
    
    scanExpressions();
    
    tft.setCursor(10, 100);
    if (numExpressions > 0) {
        tft.setTextColor(TFT_GREEN);
        tft.printf("Found %d expressions", numExpressions);
        
        tft.setTextColor(TFT_YELLOW);
        tft.setCursor(10, 120);
        tft.println("Touch to change");
        
        delay(1500);
        
        // Start playing first expression
        playExpression(0);
    } else {
        tft.setTextColor(TFT_RED);
        tft.println("No expressions!");
        tft.setCursor(10, 115);
        tft.println("Convert MP4 files first:");
        tft.setCursor(10, 130);
        tft.println("tools/convert_mp4_to_rgb565.py");
    }
    
    Serial.println("\n============================================");
    Serial.println("🎮 Touch sensor to change expression");
    Serial.println("============================================\n");
}

void loop() {
    // Handle touch to change expression
    if (digitalRead(TOUCH_PIN) == HIGH) {
        if (millis() - lastTouchTime > 500) {  // Debounce
            lastTouchTime = millis();
            Serial.println("👆 Touch detected - next expression");
            nextExpression();
        }
    }
    
    // Play animation frames at correct FPS
    if (player->isPlaying()) {
        unsigned long now = millis();
        if (now - lastFrameTime >= player->getFrameInterval()) {
            lastFrameTime = now;
            
            if (!player->playFrame()) {
                Serial.println("⏹️ Expression finished");
                // Play next if not looping
                if (!player->getLoop()) {
                    nextExpression();
                }
            }
        }
    }
    
    // Small delay to prevent CPU hogging
    delay(1);
}

