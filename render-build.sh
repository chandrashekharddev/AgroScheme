#!/usr/bin/env bash
# render-build.sh - Install system dependencies for OCR and force pre-built wheels

set -e  # exit on error

echo "🚀 Installing system dependencies for scipy and OCR..."

# Update package list
apt-get update

# Install build dependencies for scipy and OpenCV
apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config

# Upgrade pip and set options to prefer pre-built wheels
pip install --upgrade pip wheel setuptools

# Force pip to use pre-built wheels by setting platform
pip install --only-binary :all: scipy numpy

# Now install the rest of requirements
pip install -r requirements.txt

echo "✅ Build complete!"
