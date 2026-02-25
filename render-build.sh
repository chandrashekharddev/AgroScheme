#!/usr/bin/env bash
# render-build.sh - Complete build script for Render deployment

set -e  # exit on error

echo "🚀 Starting Render build process..."
echo "📦 Installing system dependencies for OCR and scipy..."

# Update package list
apt-get update

# Install ALL required system dependencies
apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    unzip \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    pkg-config \
    python3-dev

echo "✅ System dependencies installed"

# Upgrade pip and build tools
echo "📦 Upgrading pip and build tools..."
pip install --upgrade pip wheel setuptools

# Pre-install numpy and scipy from wheels first
echo "📦 Pre-installing numpy and scipy from wheels..."
pip install --only-binary :all: numpy==1.24.3 scipy==1.10.1

# Install requirements
echo "📦 Installing Python requirements..."
pip install -r requirements.txt

# Create uploads directory
echo "📁 Creating uploads directory..."
mkdir -p /opt/render/project/src/uploads

echo "✅ Build complete!"
