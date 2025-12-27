"""
MP4 to RGB565 Binary Converter for ESP32 TFT Display
=====================================================

This script converts MP4 video files to RGB565 binary format (.bin) 
that can be played on ESP32 with TFT display.

Usage:
    python convert_mp4_to_rgb565.py --input <folder> --output <folder>
    
Example:
    python convert_mp4_to_rgb565.py --input "D:\\Expression" --output "D:\\Expression_RGB565"
    python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Expression_RGB565" -w 120 -h 160 -f 15

Output Structure:
    <output_folder>/
    ├── Burger/
    │   ├── Burger.bin         # RGB565 binary data
    │   └── Burger_manifest.txt  # Metadata (width, height, fps, frames)
    ├── Love/
    │   ├── love1.bin
    │   ├── love1_manifest.txt
    │   └── ...

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

# Configuration
TARGET_WIDTH = 240   # TFT display width (use 120 for half res)
TARGET_HEIGHT = 320  # TFT display height (use 160 for half res)
TARGET_FPS = 15      # Target framerate (10-20 recommended)


def rgb888_to_rgb565(r, g, b):
    """Convert RGB888 to RGB565 (little endian for ESP32)"""
    # RGB565: RRRRRGGG GGGBBBBB
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    # Return as little endian (low byte first)
    return rgb565 & 0xFF, (rgb565 >> 8) & 0xFF


def convert_frame_to_rgb565(frame, target_width, target_height):
    """Convert a video frame to RGB565 binary data"""
    # Resize frame to target dimensions
    resized = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)
    
    # Convert BGR to RGB
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    
    # Convert to RGB565 binary
    binary_data = bytearray()
    for y in range(target_height):
        for x in range(target_width):
            r, g, b = rgb[y, x]
            low, high = rgb888_to_rgb565(r, g, b)
            binary_data.append(low)
            binary_data.append(high)
    
    return bytes(binary_data)


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
    
    # Calculate frame skip to achieve target FPS
    frame_skip = max(1, int(original_fps / target_fps))
    expected_frames = total_frames // frame_skip
    
    print(f"    Original: {original_width}x{original_height} @ {original_fps:.1f}fps, {total_frames} frames")
    print(f"    Target:   {target_width}x{target_height} @ {target_fps}fps, ~{expected_frames} frames")
    
    # Convert frames
    binary_data = bytearray()
    frame_count = 0
    frame_index = 0
    
    pbar = tqdm(total=expected_frames, desc="    Converting", unit="frame")
    
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
    
    # Write binary file
    with open(output_bin_path, 'wb') as f:
        f.write(binary_data)
    
    # Write manifest file
    with open(output_manifest_path, 'w') as f:
        f.write(f"# Manifest for {input_path.name}\n")
        f.write(f"width={target_width}\n")
        f.write(f"height={target_height}\n")
        f.write(f"fps={target_fps}\n")
        f.write(f"frames={frame_count}\n")
        f.write(f"loop=1\n")
    
    file_size_mb = len(binary_data) / (1024 * 1024)
    frame_size_kb = (target_width * target_height * 2) / 1024
    
    print(f"    ✅ Saved: {output_bin_path.name} ({file_size_mb:.2f} MB, {frame_count} frames)")
    print(f"       Frame size: {frame_size_kb:.1f} KB")
    
    return True


def process_folder(input_folder, output_folder, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT, target_fps=TARGET_FPS):
    """Process all MP4 files in a folder structure"""
    
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    if not input_path.exists():
        print(f"❌ Input folder does not exist: {input_folder}")
        return
    
    # Create output folder
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"MP4 to RGB565 Converter")
    print(f"{'='*60}")
    print(f"Input:  {input_folder}")
    print(f"Output: {output_folder}")
    print(f"Target: {target_width}x{target_height} @ {target_fps}fps")
    print(f"{'='*60}\n")
    
    # Find all MP4 files (case-insensitive, avoid duplicates on Windows)
    mp4_files_set = set()
    for f in input_path.rglob("*"):
        if f.suffix.lower() == ".mp4" and f.is_file():
            mp4_files_set.add(f)
    mp4_files = sorted(list(mp4_files_set))
    
    if not mp4_files:
        print("❌ No MP4 files found!")
        return
    
    print(f"Found {len(mp4_files)} MP4 files\n")
    
    converted = 0
    failed = 0
    
    for mp4_file in mp4_files:
        # Get relative path from input folder
        rel_path = mp4_file.relative_to(input_path)
        
        # Create output directory structure
        output_dir = output_path / rel_path.parent
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
    print(f"❌ Failed: {failed}")
    print(f"{'='*60}")
    
    # Create a summary manifest
    summary_path = output_path / "expressions_manifest.txt"
    with open(summary_path, 'w') as f:
        f.write(f"# Expression Summary\n")
        f.write(f"# Generated by convert_mp4_to_rgb565.py\n")
        f.write(f"total_expressions={converted}\n")
        f.write(f"width={target_width}\n")
        f.write(f"height={target_height}\n")
        f.write(f"fps={target_fps}\n")
        f.write(f"\n# Files:\n")
        for mp4_file in mp4_files:
            rel_path = mp4_file.relative_to(input_path)
            base_name = mp4_file.stem
            bin_path = rel_path.parent / f"{base_name}.bin"
            f.write(f"{bin_path}\n")
    
    print(f"\n📄 Summary saved to: {summary_path}")
    print(f"\n🎉 Done! Copy the '{output_folder}' contents to your SD card.")


def main():
    parser = argparse.ArgumentParser(
        description='Convert MP4 videos to RGB565 binary format for ESP32 TFT display',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python convert_mp4_to_rgb565.py -i "D:\\Expression" -o "D:\\Expression_RGB565"
  python convert_mp4_to_rgb565.py --input "C:\\Videos" --output "C:\\Output" -w 120 -h 160 -f 15
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

