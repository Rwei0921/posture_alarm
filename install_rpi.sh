#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

echo "[1/5] Installing system packages..."
$SUDO apt-get update
$SUDO apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  libopenblas-dev \
  libjpeg-dev \
  libtiff-dev \
  libopenjp2-7 \
  libavcodec-dev \
  libavformat-dev \
  libswscale-dev \
  libgtk-3-dev \
  libglib2.0-0 \
  libgl1 \
  i2c-tools \
  v4l-utils \
  rpicam-apps \
  python3-lgpio \
  python3-opencv \
  python3-picamera2

echo "[2/5] Preparing Python virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv --system-site-packages
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/5] Upgrading pip toolchain..."
python -m pip install --upgrade pip setuptools wheel

echo "[4/5] Installing common Python dependencies..."
python -m pip install \
  "requests>=2.31.0" \
  "smbus2>=0.4.3" \
  "gpiozero>=2.0"

echo "[5/5] Installing MediaPipe..."
python -m pip uninstall -y mediapipe mediapipe-rpi4 >/dev/null 2>&1 || true
if python -m pip install --no-cache-dir "mediapipe>=0.10.0"; then
  if python -c "import mediapipe as mp; print(mp.__version__)" >/dev/null 2>&1; then
    echo "MediaPipe installed successfully."
  else
    echo "Installed mediapipe is not importable on this Python. Trying mediapipe-rpi4..."
    python -m pip uninstall -y mediapipe >/dev/null 2>&1 || true
    python -m pip install --no-cache-dir mediapipe-rpi4
  fi
else
  echo "Official mediapipe wheel failed. Trying mediapipe-rpi4..."
  python -m pip install --no-cache-dir mediapipe-rpi4
fi

echo "\nDone."
echo "Activate env: source .venv/bin/activate"
echo "Run app: python main.py"
