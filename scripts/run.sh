#!/usr/bin/env bash
# Launch the rideday-radar dashboard. Open http://127.0.0.1:8765
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python app.py
