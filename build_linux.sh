#!/bin/bash

# LoadHunter Linux Build Script
# This script packages the application into a standalone binary for Linux.

set -e

echo "🚀 Starting LoadHunter Build Process for Linux..."

# 1. Environment Check
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        echo "python-pointing-to-venv: Found 'venv' folder. Activating..."
        source venv/bin/activate
    else
        echo "⚠️ No virtual environment detected."
        echo "Modern Linux requires a venv to build. Please run:"
        echo "  python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        echo "Then try running this script again."
        exit 1
    fi
fi

# 2. Install dependencies
echo "📦 Ensuring dependencies are installed in venv..."
pip install -r requirements.txt --quiet

# 3. Run PyInstaller
echo "🔨 Building standalone binary with PyInstaller..."
# Ensure we use the pyinstaller from the venv
python3 -m PyInstaller main.spec --noconfirm

# 3. Success message
echo "✅ Build Complete!"
echo "📍 Your standalone binary is located at: $(pwd)/dist/LoadHunter"
echo ""
echo "To run the app:"
echo "./dist/LoadHunter"

# Optional: Create a .desktop entry
read -p "Do you want to create a desktop shortcut? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DESKTOP_FILE=~/.local/share/applications/loadhunter.desktop
    echo "[Desktop Entry]" > $DESKTOP_FILE
    echo "Name=LoadHunter" >> $DESKTOP_FILE
    echo "Exec=$(pwd)/dist/LoadHunter" >> $DESKTOP_FILE
    echo "Type=Application" >> $DESKTOP_FILE
    echo "Terminal=false" >> $DESKTOP_FILE
    echo "Categories=Logistics;Utility;" >> $DESKTOP_FILE
    echo "Comment=Modular Logistics Filter for Uzbekistan" >> $DESKTOP_FILE
    chmod +x $DESKTOP_FILE
    echo "✨ Desktop shortcut created at $DESKTOP_FILE"
fi
