#!/usr/bin/env python3
"""
Audio debugging script to test ALSA device capture
"""
import subprocess
import os

def list_alsa_devices():
    """List all ALSA capture devices"""
    print("=== ALSA Capture Devices ===")
    result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

def test_ffmpeg_capture(device="hw:1,0", duration=3):
    """Test FFmpeg audio capture from specified device"""
    print(f"\n=== Testing FFmpeg capture from {device} for {duration}s ===")
    cmd = [
        "ffmpeg",
        "-f", "alsa",
        "-i", device,
        "-ac", "1",
        "-ar", "16000",
        "-t", str(duration),
        "-f", "s16le",
        "/tmp/test_audio.raw"
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size = os.path.getsize("/tmp/test_audio.raw")
        print(f"✅ Success! Captured {size} bytes")
        expected = 16000 * 2 * duration  # 16kHz * 2 bytes * duration
        print(f"   Expected ~{expected} bytes for {duration}s")
        if size < expected * 0.5:
            print("   ⚠️  Warning: Captured significantly less data than expected")
    else:
        print(f"❌ Failed with return code {result.returncode}")
        print("STDERR:", result.stderr)

def test_current_config():
    """Test the device configured in environment"""
    device = os.environ.get("ALSA_DEVICE", "hw:1,0")
    print(f"\n=== Current config: ALSA_DEVICE={device} ===")
    test_ffmpeg_capture(device, 3)

if __name__ == "__main__":
    list_alsa_devices()
    test_current_config()

    print("\n=== Recommendations ===")
    print("1. Check if the device shown above matches your ReSpeaker")
    print("2. Try other devices if capture failed (e.g., hw:0,0, hw:2,0)")
    print("3. Set ALSA_DEVICE environment variable if needed")
    print("4. Check permissions: user should be in 'audio' group")
