#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCHER_DIR="$PROJECT_DIR/launcher"

echo "Building Go launchers for all platforms..."

cd "$LAUNCHER_DIR"

go mod tidy

make clean
make all

echo ""
echo "Build complete! Launchers are in: $LAUNCHER_DIR/build/"
ls -la "$LAUNCHER_DIR/build/"
