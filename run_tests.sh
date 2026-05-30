#!/bin/bash
set -e
cd /workspace
export PYTHONPATH=/workspace/src

# Install deps if not already done
pip3 install pytest pytest-cov 2>/dev/null || true

# Run unit tests only (no OE runtime needed)
python3 -m pytest tests/unit/ -v --tb=short 2>&1
