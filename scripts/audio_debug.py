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

def get_device_info(device="hw:1,0"):
    """Get detailed device capabilities"""
    print(f"\n=== Device Info for {device} ===")
    result = subprocess.run(
        ["arecord", "-D", device, "--dump-hw-params"],
        capture_output=True,
        text=True,
        timeout=2
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

def test_ffmpeg_with_options(device="hw:1,0", duration=2, extra_opts=None):
    """Test FFmpeg audio capture with specific options"""
    opts_desc = " ".join(extra_opts) if extra_opts else "default"
    print(f"\n=== Testing FFmpeg: {device} with {opts_desc} ===")

    cmd = ["ffmpeg", "-f", "alsa"]
    if extra_opts:
        cmd.extend(extra_opts)
    cmd.extend([
        "-i", device,
        "-ac", "1",
        "-ar", "16000",
        "-t", str(duration),
        "-f", "s16le",
        "/tmp/test_audio.raw"
    ])

    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size = os.path.getsize("/tmp/test_audio.raw")
        expected = 16000 * 2 * duration
        print(f"✅ Success! Captured {size} bytes (expected ~{expected})")
        return True
    else:
        print(f"❌ Failed with return code {result.returncode}")
        # Only show relevant error lines
        for line in result.stderr.split('\n'):
            if 'alsa' in line.lower() or 'error' in line.lower() or 'invalid' in line.lower():
                print(f"   {line}")
        return False

def test_plughw(device_num="1,0", duration=2):
    """Test with plughw instead of hw (allows ALSA to do format conversion)"""
    print(f"\n=== Testing with plughw:{device_num} (ALSA format conversion) ===")
    cmd = [
        "ffmpeg",
        "-f", "alsa",
        "-i", f"plughw:{device_num}",
        "-ac", "1",
        "-ar", "16000",
        "-t", str(duration),
        "-f", "s16le",
        "/tmp/test_audio.raw"
    ]
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size = os.path.getsize("/tmp/test_audio.raw")
        expected = 16000 * 2 * duration
        print(f"✅ Success! Captured {size} bytes (expected ~{expected})")
        print(f"   👉 Use: ALSA_DEVICE=plughw:{device_num}")
        return True
    else:
        print(f"❌ Failed")
        for line in result.stderr.split('\n'):
            if 'alsa' in line.lower() or 'error' in line.lower():
                print(f"   {line}")
        return False

def test_configurations():
    """Test different configurations to find what works"""
    device = os.environ.get("ALSA_DEVICE", "hw:1,0")
    device_num = device.replace("hw:", "")

    print(f"\n{'='*60}")
    print("TESTING DIFFERENT CONFIGURATIONS")
    print(f"{'='*60}")

    configs = [
        ("Default hw device", device, None),
        ("With sample_rate option", device, ["-sample_rate", "16000"]),
        ("plughw device", f"plughw:{device_num}", None),
    ]

    working = []
    for name, dev, opts in configs:
        if "plughw" in dev:
            success = test_plughw(device_num)
        else:
            success = test_ffmpeg_with_options(dev, duration=2, extra_opts=opts)

        if success:
            working.append((name, dev, opts))

    return working

if __name__ == "__main__":
    list_alsa_devices()

    device = os.environ.get("ALSA_DEVICE", "hw:1,0")
    get_device_info(device)

    working = test_configurations()

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    if working:
        print("✅ Working configurations:")
        for name, dev, opts in working:
            print(f"   - {name}: ALSA_DEVICE={dev}")
        print(f"\n👉 Recommended: export ALSA_DEVICE={working[0][1]}")
    else:
        print("❌ No working configurations found")
        print("\nTroubleshooting:")
        print("1. Check permissions: groups (should show 'audio')")
        print("2. Check if device is in use: lsof /dev/snd/*")
        print("3. Try: arecord -D hw:1,0 -f S16_LE -r 16000 -c 1 test.wav")
