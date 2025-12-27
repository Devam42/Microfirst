"""
MP4 to RGB565 Binary Converter for ESP32 TFT Display
=====================================================

OPTIMIZED VERSION - Designed for smooth, real-time playback!

This script converts MP4 video files to RGB565 binary format (.bin) 
that can be played on ESP32 with TFT display at full speed.

Key Features:
- Uses 128x160 resolution by default (fits in ESP32 RAM for single-read)
- Frame size: 40,960 bytes (~40KB) - perfect for ESP32 heap
- Enables 30+ FPS smooth playback
- Preserves original colors accurately

Usage:
    python convert_mp4_to_rgb565.py --input <folder> --output <folder>
    
Example:
    python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Expression_RGB565"
    python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Expression_RGB565" -w 128 -ht 160 -f 20

Resolution Options:
    - 128x160 (default): 40KB/frame - FASTEST, fits in RAM
    - 160x200: 64KB/frame - Good balance
    - 240x320: 154KB/frame - Needs PSRAM or chunk-based (slower)

Output Structure:
    <output_folder>/
    ├── Expression/           # Keep this name for SD card
    │   ├── Burger/
    │   │   ├── Burger.bin
    │   │   └── Burger_manifest.txt
    │   ├── Love/
    │   │   ├── love1.bin
    │   │   └── love1_manifest.txt

Requirements:
    pip install opencv-python numpy tqdm

Author: Microbot Project
"""

import os
import sys
import argparse
import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm

# ============================================================================
# OPTIMIZED CONFIGURATION - For smooth real-time playback
# ============================================================================
# 128x160 = 40,960 bytes per frame - fits perfectly in ESP32 RAM!
# This allows single SD read per frame = maximum speed

TARGET_WIDTH = 128    # Optimized width (fits in RAM)
TARGET_HEIGHT = 160   # Optimized height (fits in RAM)
TARGET_FPS = 20       # Target framerate (20fps = smooth animation)

# Frame size info:
# 128x160x2 = 40,960 bytes (~40KB) - ESP32 can buffer this!
# 160x200x2 = 64,000 bytes (~64KB) - Still fits in most ESP32s
# 240x320x2 = 153,600 bytes (~154KB) - Needs PSRAM or chunking


def rgb888_to_rgb565_swapped(r, g, b):
    """
    Convert RGB888 to RGB565 with byte swap for TFT_eSPI
    
    TFT_eSPI with setSwapBytes(true) expects: HIGH byte first, then LOW byte
    This matches how pushImage reads uint16_t arrays
    """
    # RGB565: RRRRRGGG GGGBBBBB
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    
    # Return as bytes for direct file write (high byte first for swapped mode)
    # This way ESP32 can use setSwapBytes(true) and get correct colors
    high = (rgb565 >> 8) & 0xFF
    low = rgb565 & 0xFF
    return high, low


def convert_frame_to_rgb565(frame, target_width, target_height):
    """Convert a video frame to RGB565 binary data (optimized for TFT_eSPI)"""
    # Resize frame to target dimensions with high quality
    resized = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
    
    # Convert BGR (OpenCV format) to RGB
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    
    # Convert to RGB565 binary - optimized with numpy
    # This is much faster than pixel-by-pixel loop
    r = rgb[:, :, 0].astype(np.uint16)
    g = rgb[:, :, 1].astype(np.uint16)
    b = rgb[:, :, 2].astype(np.uint16)
    
    # RGB565 conversion
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    
    # Swap bytes for TFT_eSPI compatibility
    # High byte first, low byte second
    high = ((rgb565 >> 8) & 0xFF).astype(np.uint8)
    low = (rgb565 & 0xFF).astype(np.uint8)
    
    # Interleave high and low bytes
    binary_data = np.empty((target_height, target_width, 2), dtype=np.uint8)
    binary_data[:, :, 0] = high
    binary_data[:, :, 1] = low
    
    return binary_data.tobytes()


def convert_video(input_path, output_bin_path, output_manifest_path, target_width, target_height, target_fps):
    """Convert a single MP4 file to RGB565 binary format"""
    
    # Open video
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        print(f"    ❌ Could not open: {input_path}")
        return False
    
    # Get video properties
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    if original_fps <= 0:
        original_fps = 30  # Default if unknown
    
    # Calculate frame skip to achieve target FPS
    frame_skip = max(1, int(round(original_fps / target_fps)))
    expected_frames = total_frames // frame_skip
    
    # Calculate sizes
    frame_size_bytes = target_width * target_height * 2
    estimated_total_mb = (expected_frames * frame_size_bytes) / (1024 * 1024)
    
    print(f"    Original: {original_width}x{original_height} @ {original_fps:.1f}fps, {total_frames} frames")
    print(f"    Target:   {target_width}x{target_height} @ {target_fps}fps, ~{expected_frames} frames")
    print(f"    Frame size: {frame_size_bytes:,} bytes ({frame_size_bytes/1024:.1f} KB)")
    print(f"    Estimated file size: {estimated_total_mb:.2f} MB")
    
    # Convert frames
    binary_data = bytearray()
    frame_count = 0
    frame_index = 0
    
    pbar = tqdm(total=expected_frames, desc="    Converting", unit="frame", ncols=70)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Skip frames to achieve target FPS
        if frame_index % frame_skip == 0:
            frame_rgb565 = convert_frame_to_rgb565(frame, target_width, target_height)
            binary_data.extend(frame_rgb565)
            frame_count += 1
            pbar.update(1)
        
        frame_index += 1
    
    pbar.close()
    cap.release()
    
    if frame_count == 0:
        print(f"    ❌ No frames converted!")
        return False
    
    # Write binary file
    with open(output_bin_path, 'wb') as f:
        f.write(binary_data)
    
    # Write manifest file
    with open(output_manifest_path, 'w') as f:
        f.write(f"# Manifest for {input_path.name}\n")
        f.write(f"# Optimized for ESP32 single-read playback\n")
        f.write(f"width={target_width}\n")
        f.write(f"height={target_height}\n")
        f.write(f"fps={target_fps}\n")
        f.write(f"frames={frame_count}\n")
        f.write(f"loop=1\n")
        f.write(f"# Frame size: {frame_size_bytes} bytes\n")
    
    file_size_mb = len(binary_data) / (1024 * 1024)
    
    print(f"    ✅ Saved: {output_bin_path.name}")
    print(f"       Size: {file_size_mb:.2f} MB, {frame_count} frames")
    print(f"       Frame: {frame_size_bytes/1024:.1f} KB (fits in ESP32 RAM: {'YES ✓' if frame_size_bytes <= 65000 else 'NO - needs chunking'})")
    
    return True


def process_folder(input_folder, output_folder, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT, target_fps=TARGET_FPS):
    """Process all MP4 files in a folder structure"""
    
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    if not input_path.exists():
        print(f"❌ Input folder does not exist: {input_folder}")
        return
    
    # Create output folder with Expression subfolder (for SD card)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"❌ Cannot create output folder: {output_folder}")
        print(f"   Error: {e}")
        print(f"   Try using a path on C: drive, e.g.: -o \"C:\\Microbot\\Expression_RGB565\"")
        return
    
    expression_output = output_path / "Expression"
    expression_output.mkdir(parents=True, exist_ok=True)
    
    frame_size = target_width * target_height * 2
    can_single_read = frame_size <= 65000
    
    print(f"\n{'='*60}")
    print(f"🎬 MP4 to RGB565 Converter - OPTIMIZED")
    print(f"{'='*60}")
    print(f"Input:  {input_folder}")
    print(f"Output: {output_folder}/Expression/")
    print(f"Target: {target_width}x{target_height} @ {target_fps}fps")
    print(f"Frame:  {frame_size:,} bytes ({frame_size/1024:.1f} KB)")
    print(f"Mode:   {'SINGLE-READ (FAST!) ✓' if can_single_read else 'CHUNKED (slower)'}")
    print(f"{'='*60}\n")
    
    # Find all MP4 files (case-insensitive, avoid duplicates on Windows)
    mp4_files_set = set()
    for f in input_path.rglob("*"):
        if f.suffix.lower() == ".mp4" and f.is_file():
            # Use resolved path to avoid duplicates
            mp4_files_set.add(f.resolve())
    mp4_files = sorted(list(mp4_files_set))
    
    if not mp4_files:
        print("❌ No MP4 files found!")
        return
    
    print(f"📁 Found {len(mp4_files)} MP4 files\n")
    
    converted = 0
    failed = 0
    
    for mp4_file in mp4_files:
        # Get relative path from input folder
        try:
            rel_path = mp4_file.relative_to(input_path.resolve())
        except ValueError:
            rel_path = Path(mp4_file.name)
        
        # Create output directory structure under Expression/
        output_dir = expression_output / rel_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Output file names
        base_name = mp4_file.stem
        output_bin = output_dir / f"{base_name}.bin"
        output_manifest = output_dir / f"{base_name}_manifest.txt"
        
        print(f"📹 {rel_path}")
        
        if convert_video(mp4_file, output_bin, output_manifest, target_width, target_height, target_fps):
            converted += 1
        else:
            failed += 1
        
        print()
    
    print(f"{'='*60}")
    print(f"✅ Converted: {converted}")
    if failed > 0:
        print(f"❌ Failed: {failed}")
    print(f"{'='*60}")
    
    # Create a summary manifest
    summary_path = expression_output / "expressions_summary.txt"
    with open(summary_path, 'w') as f:
        f.write(f"# Expression Summary - OPTIMIZED\n")
        f.write(f"# Generated by convert_mp4_to_rgb565.py\n")
        f.write(f"# Copy 'Expression' folder to SD card root\n")
        f.write(f"#\n")
        f.write(f"total_expressions={converted}\n")
        f.write(f"width={target_width}\n")
        f.write(f"height={target_height}\n")
        f.write(f"fps={target_fps}\n")
        f.write(f"frame_size={target_width * target_height * 2}\n")
        f.write(f"single_read_mode={'yes' if can_single_read else 'no'}\n")
        f.write(f"\n# Files:\n")
        for mp4_file in mp4_files:
            try:
                rel_path = mp4_file.relative_to(input_path.resolve())
            except ValueError:
                rel_path = Path(mp4_file.name)
            base_name = mp4_file.stem
            bin_path = rel_path.parent / f"{base_name}.bin"
            f.write(f"/Expression/{bin_path}\n")
    
    print(f"\n📄 Summary saved to: {summary_path}")
    print(f"\n🎉 Done!")
    print(f"\n📋 Next steps:")
    print(f"   1. Copy '{output_path}/Expression' folder to your SD card")
    print(f"   2. SD card should have: /Expression/Burger/Burger.bin etc.")
    print(f"   3. Upload the updated ESP32 code")
    print(f"   4. Enjoy smooth {target_fps}fps playback! 🚀")


def main():
    parser = argparse.ArgumentParser(
        description='Convert MP4 videos to RGB565 binary format for ESP32 TFT display (OPTIMIZED)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Resolution Options:
  128x160  - 40KB/frame  - FASTEST, single SD read per frame (RECOMMENDED)
  160x200  - 64KB/frame  - Good balance, still fits in RAM
  240x320  - 154KB/frame - Full resolution, needs PSRAM or chunking

Examples:
  python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Output"
  python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Output" -w 128 -ht 160 -f 20
  python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Output" -w 160 -ht 200 -f 15
        '''
    )
    
    parser.add_argument('-i', '--input', required=True, 
                        help='Input folder containing MP4 files')
    parser.add_argument('-o', '--output', required=True,
                        help='Output folder for converted files')
    parser.add_argument('-w', '--width', type=int, default=TARGET_WIDTH,
                        help=f'Target width (default: {TARGET_WIDTH})')
    parser.add_argument('-ht', '--height', type=int, default=TARGET_HEIGHT,
                        help=f'Target height (default: {TARGET_HEIGHT})')
    parser.add_argument('-f', '--fps', type=int, default=TARGET_FPS,
                        help=f'Target FPS (default: {TARGET_FPS})')
    
    args = parser.parse_args()
    
    process_folder(args.input, args.output, args.width, args.height, args.fps)


if __name__ == "__main__":
    main()
