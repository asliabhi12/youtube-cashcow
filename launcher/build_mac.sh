#!/usr/bin/env bash
# Build script for packaging CashCow Desktop Launcher on macOS into a standalone .app

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -f "${VENV_PYTHON}" ]; then
  VENV_PYTHON="python3"
fi

echo "========================================================"
echo " Building CashCow Desktop Launcher for macOS"
echo " Project Root: ${PROJECT_ROOT}"
echo " Python: ${VENV_PYTHON}"
echo "========================================================"

cd "${PROJECT_ROOT}"

# Install pyinstaller if missing
"${VENV_PYTHON}" -m pip install -q pyinstaller

# Run PyInstaller
"${VENV_PYTHON}" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "CashCow Launcher" \
  --paths "${PROJECT_ROOT}" \
  --add-data "launcher:launcher" \
  launcher/main.py

echo ""
echo "========================================================"
echo " SUCCESS: Built macOS Application Bundle!"
echo " App location: ${PROJECT_ROOT}/dist/CashCow Launcher.app"
echo "========================================================"
echo "To create a Desktop shortcut, run:"
echo "  ln -s \"${PROJECT_ROOT}/dist/CashCow Launcher.app\" ~/Desktop/CashCow"
echo "========================================================"
