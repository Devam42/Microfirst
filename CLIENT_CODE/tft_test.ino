/*
 * TFT Display Test - Simple test to verify TFT works
 * This will show different colors on the screen
 */

#include <TFT_eSPI.h>
#include <SPI.h>

TFT_eSPI tft = TFT_eSPI();

// Backlight pin - change to match your wiring!
#define TFT_LED 15

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("TFT Display Test");
  Serial.println("========================================\n");
  
  // Print the TFT configuration (from User_Setup.h)
  Serial.println("TFT Configuration (from User_Setup.h):");
  Serial.println("If display doesn't work, edit User_Setup.h in:");
  Serial.println("C:\\Users\\dkath\\OneDrive\\Documents\\Arduino\\libraries\\TFT_eSPI\\");
  Serial.println("");
  
  // Turn on backlight
  pinMode(TFT_LED, OUTPUT);
  digitalWrite(TFT_LED, HIGH);
  Serial.printf("Backlight ON (GPIO%d)\n", TFT_LED);
  
  // Initialize TFT
  Serial.println("Initializing TFT...");
  tft.init();
  tft.setRotation(0);
  
  Serial.printf("TFT Width: %d, Height: %d\n", tft.width(), tft.height());
  Serial.println("If you see colors cycling, TFT is working!");
  Serial.println("");
}

void loop() {
  // Cycle through colors
  Serial.println("RED");
  tft.fillScreen(TFT_RED);
  delay(1000);
  
  Serial.println("GREEN");
  tft.fillScreen(TFT_GREEN);
  delay(1000);
  
  Serial.println("BLUE");
  tft.fillScreen(TFT_BLUE);
  delay(1000);
  
  Serial.println("WHITE");
  tft.fillScreen(TFT_WHITE);
  delay(1000);
  
  Serial.println("BLACK with text");
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_CYAN);
  tft.setTextSize(3);
  tft.setCursor(30, 100);
  tft.println("MICROBOT");
  tft.setTextSize(2);
  tft.setCursor(50, 150);
  tft.println("TFT OK!");
  delay(2000);
}

