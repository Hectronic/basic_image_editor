#!/bin/bash
set -e

# Create virtual environment if it doesn't exist or is incomplete
if [ ! -f "venv/bin/activate" ]; then
    echo "Creating virtual environment..."
    rm -rf venv
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Launch the script
echo "Starting Image Editor..."
python3 main.py
