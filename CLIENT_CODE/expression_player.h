/*
 * Expression Player for ESP32 TFT
 * ================================
 * Plays RGB565 binary animation files from SD card
 * 
 * File format:
 * - Raw RGB565 pixels, little endian
 * - Frame by frame, no headers
 * - Accompanied by manifest.txt with metadata
 */

#ifndef EXPRESSION_PLAYER_H
#define EXPRESSION_PLAYER_H

#include <Arduino.h>
#include <SD.h>
#include <TFT_eSPI.h>

// Expression configuration
#define EXPR_MAX_PATH 64
#define EXPR_FRAME_WIDTH 240
#define EXPR_FRAME_HEIGHT 320
#define EXPR_FRAME_SIZE (EXPR_FRAME_WIDTH * EXPR_FRAME_HEIGHT * 2)  // 153600 bytes

// We'll read in chunks since full frame won't fit in RAM
#define EXPR_CHUNK_LINES 20  // Read 20 lines at a time
#define EXPR_CHUNK_SIZE (EXPR_FRAME_WIDTH * EXPR_CHUNK_LINES * 2)  // 9600 bytes per chunk

class ExpressionPlayer {
public:
    ExpressionPlayer(TFT_eSPI* display);
    
    // Load expression from bin file
    bool load(const char* binPath);
    
    // Unload current expression
    void unload();
    
    // Play one frame, returns false if finished (non-loop) or error
    bool playFrame();
    
    // Check if currently playing
    bool isPlaying() { return _isPlaying; }
    
    // Get/set loop mode
    void setLoop(bool loop) { _loop = loop; }
    bool getLoop() { return _loop; }
    
    // Get info
    int getWidth() { return _width; }
    int getHeight() { return _height; }
    int getFps() { return _fps; }
    int getTotalFrames() { return _totalFrames; }
    int getCurrentFrame() { return _currentFrame; }
    
    // Frame timing
    unsigned long getFrameInterval() { return 1000 / _fps; }
    
private:
    TFT_eSPI* _tft;
    File _binFile;
    
    bool _isPlaying;
    bool _loop;
    
    int _width;
    int _height;
    int _fps;
    int _totalFrames;
    int _currentFrame;
    
    char _currentPath[EXPR_MAX_PATH];
    
    // Buffer for reading chunks
    uint8_t _chunkBuffer[EXPR_CHUNK_SIZE];
    
    bool loadManifest(const char* binPath);
    bool displayFrame();
};

// Implementation

ExpressionPlayer::ExpressionPlayer(TFT_eSPI* display) {
    _tft = display;
    _isPlaying = false;
    _loop = true;
    _width = EXPR_FRAME_WIDTH;
    _height = EXPR_FRAME_HEIGHT;
    _fps = 15;
    _totalFrames = 0;
    _currentFrame = 0;
    _currentPath[0] = '\0';
}

bool ExpressionPlayer::loadManifest(const char* binPath) {
    // Construct manifest path from bin path
    // e.g., /Expression/Burger/Burger.bin -> /Expression/Burger/Burger_manifest.txt
    String manifestPath = String(binPath);
    manifestPath.replace(".bin", "_manifest.txt");
    
    File mf = SD.open(manifestPath.c_str());
    if (!mf) {
        // Try alternate naming: folder/manifest.txt
        int lastSlash = manifestPath.lastIndexOf('/');
        if (lastSlash > 0) {
            manifestPath = manifestPath.substring(0, lastSlash) + "/manifest.txt";
            mf = SD.open(manifestPath.c_str());
        }
    }
    
    if (!mf) {
        Serial.printf("⚠️ No manifest found, using defaults\n");
        // Use defaults
        _width = EXPR_FRAME_WIDTH;
        _height = EXPR_FRAME_HEIGHT;
        _fps = 15;
        _loop = true;
        
        // Estimate frames from file size
        File binFile = SD.open(binPath);
        if (binFile) {
            long fileSize = binFile.size();
            long frameSize = _width * _height * 2;
            _totalFrames = fileSize / frameSize;
            binFile.close();
            Serial.printf("   Estimated %d frames from file size\n", _totalFrames);
        }
        return true;
    }
    
    Serial.printf("📄 Reading manifest: %s\n", manifestPath.c_str());
    
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
        
        if (key == "width") _width = val.toInt();
        else if (key == "height") _height = val.toInt();
        else if (key == "fps") _fps = val.toInt();
        else if (key == "frames") _totalFrames = val.toInt();
        else if (key == "loop") _loop = (val.toInt() != 0);
    }
    
    mf.close();
    
    Serial.printf("   Size: %dx%d, FPS: %d, Frames: %d, Loop: %s\n",
                  _width, _height, _fps, _totalFrames, _loop ? "yes" : "no");
    
    return true;
}

bool ExpressionPlayer::load(const char* binPath) {
    unload();
    
    Serial.printf("🎬 Loading expression: %s\n", binPath);
    
    // Load manifest first
    if (!loadManifest(binPath)) {
        return false;
    }
    
    // Open binary file
    _binFile = SD.open(binPath);
    if (!_binFile) {
        Serial.printf("❌ Could not open: %s\n", binPath);
        return false;
    }
    
    strncpy(_currentPath, binPath, EXPR_MAX_PATH - 1);
    _currentFrame = 0;
    _isPlaying = true;
    
    Serial.printf("✅ Expression loaded! Ready to play.\n");
    
    return true;
}

void ExpressionPlayer::unload() {
    if (_binFile) {
        _binFile.close();
    }
    _isPlaying = false;
    _currentFrame = 0;
    _currentPath[0] = '\0';
}

bool ExpressionPlayer::displayFrame() {
    if (!_binFile || !_isPlaying) return false;
    
    long frameSize = (long)_width * _height * 2;
    
    // Check if we've reached the end
    if (_totalFrames > 0 && _currentFrame >= _totalFrames) {
        if (_loop) {
            _binFile.seek(0);
            _currentFrame = 0;
        } else {
            _isPlaying = false;
            return false;
        }
    }
    
    // Also check by file position
    if (_binFile.position() >= _binFile.size()) {
        if (_loop) {
            _binFile.seek(0);
            _currentFrame = 0;
        } else {
            _isPlaying = false;
            return false;
        }
    }
    
    // Read and display frame in chunks
    int linesPerChunk = EXPR_CHUNK_LINES;
    int chunkSize = _width * linesPerChunk * 2;
    
    for (int y = 0; y < _height; y += linesPerChunk) {
        int linesToRead = min(linesPerChunk, _height - y);
        int bytesToRead = _width * linesToRead * 2;
        
        int bytesRead = _binFile.read(_chunkBuffer, bytesToRead);
        if (bytesRead != bytesToRead) {
            Serial.printf("⚠️ Read error at frame %d, line %d\n", _currentFrame, y);
            return false;
        }
        
        // Push to display
        // Using pushImage for efficiency
        _tft->pushImage(0, y, _width, linesToRead, (uint16_t*)_chunkBuffer);
    }
    
    _currentFrame++;
    return true;
}

bool ExpressionPlayer::playFrame() {
    return displayFrame();
}

#endif // EXPRESSION_PLAYER_H

