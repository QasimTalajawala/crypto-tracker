#!/bin/bash
# Builds a standalone Crypto Tracker.app for macOS
# Run once:  chmod +x build_mac_app.sh && ./build_mac_app.sh

set -e

echo "📦 Installing build dependencies..."
pip3 install pyinstaller pywebview streamlit requests pandas numpy -q

echo "🔨 Building Crypto Tracker.app..."
pyinstaller \
  --name "Crypto Tracker" \
  --windowed \
  --onedir \
  --noconfirm \
  --add-data "app.py:." \
  --hidden-import "streamlit" \
  --hidden-import "streamlit.web.cli" \
  --hidden-import "webview" \
  --hidden-import "pandas" \
  --hidden-import "numpy" \
  --hidden-import "requests" \
  desktop_app.py

echo ""
echo "✅ Done! Your app is at:  dist/Crypto Tracker/Crypto Tracker.app"
echo "   You can drag it to /Applications to install it."
