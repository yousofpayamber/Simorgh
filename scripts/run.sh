#!/usr/bin/env bash
# Simorgh - Quick setup and run script

set -e

PYTHON=${PYTHON:-python3}

echo "==> Checking Python version..."
$PYTHON -c "
import sys
if sys.version_info < (3, 10):
    print('ERROR: Python 3.10+ required (found ' + sys.version + ')')
    sys.exit(1)
print('OK:', sys.version)
"

echo "==> Installing dependencies..."
$PYTHON -m pip install -r requirements.txt --quiet

echo "==> Running tests..."
$PYTHON -m pytest tests/ -v --tb=short

echo ""
echo "==> Starting Simorgh proxy..."
$PYTHON main.py "$@"
