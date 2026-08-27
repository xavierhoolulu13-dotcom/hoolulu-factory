#!/usr/bin/env bash
set -e

echo "=== Installing Hoolulu OS (Streamlined Build) ==="

# Update Termux packages
pkg update -y && pkg upgrade -y

# Install essentials
pkg install -y git python python-pip

# Install Python deps
pip install --upgrade pip
pip install requests aiohttp websockets flask

# Run Command Center
cd core
python command_center.py

echo "=== Hoolulu OS Ready ==="
