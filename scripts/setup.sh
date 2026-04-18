#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "  BluePACS CD Creator - Setup"
echo "======================================"

# Backend setup
echo ""
echo "Setting up backend..."
cd "$PROJECT_DIR/backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example - please edit with your settings"
fi
deactivate

# Frontend setup
echo ""
echo "Setting up frontend..."
cd "$PROJECT_DIR/frontend"
npm install

# Standalone viewer binaries (OHIF + embedded web server, built in ../Viewers/standalone)
echo ""
echo "Syncing standalone viewer binaries..."
"$SCRIPT_DIR/sync_standalone.sh" || echo "(skip) populate cd_template/standalone manually - see cd_template/standalone/README.md"

echo ""
echo "======================================"
echo "  Setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env with your DICOM node settings"
echo "  2. Run: cd backend && source venv/bin/activate && python server.py"
echo "  3. Run: cd frontend && npm run dev"
echo "  4. Open http://localhost:3000"
