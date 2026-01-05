#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "=== Moderación de reseñas (localhost) v3 ==="

if [ ! -d ".venv" ]; then
  python3 -m venv .venv || python -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python app.py
