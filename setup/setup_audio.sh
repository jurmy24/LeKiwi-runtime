#!/bin/bash
# Audio Setup Script for LeKiwi
# Applies optimal mixer settings and restores ALSA state

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 0. Copy .asoundrc configuration to home directory
echo "Setting up ALSA configuration..."
if [ -f "$SCRIPT_DIR/.asoundrc" ]; then
    cp "$SCRIPT_DIR/.asoundrc" ~/.asoundrc
    echo ".asoundrc copied to home directory"
else
    echo "Warning: .asoundrc file not found in $SCRIPT_DIR"
fi

# 1. Disable Noise Gate (fixes choppy audio)
amixer -c 2 cset numid=35 0

# 2. Lower Input Boost (fixes buzzing/distortion)
amixer -c 2 cset numid=9 0
amixer -c 2 cset numid=8 0

# 3. Enable ALC (helps with consistent levels)
amixer -c 2 cset numid=26 3  # Stereo
amixer -c 2 cset numid=28 11 # Target
amixer -c 2 cset numid=27 7  # Max Gain
amixer -c 2 cset numid=29 0  # Min Gain

# 4. Set Capture Volume (Reasonable starting point)
amixer -c 2 cset numid=36 230

# 5. Enable High Pass Filter (removes low rumble)
amixer -c 2 cset numid=19 1

# 6. Ensure paths are open
amixer -c 2 cset numid=3 1   # Capture on
amixer -c 2 cset numid=50 1  # Left Boost on
amixer -c 2 cset numid=51 1  # Right Boost on

# 7. Set Speaker Volume
amixer -c 2 cset numid=13 115

echo "Audio settings and ALSA configuration applied successfully."
