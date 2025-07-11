#!/bin/bash
# Exit on error
set -e

# Install system dependencies
apt-get update
apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libx11-xcb1

# Clean up to reduce image size
apt-get clean
rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
python -m playwright install --with-deps
python -m playwright install-deps
