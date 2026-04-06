# BluePACS CD Creation

A web application for creating DICOM CD/DVDs with an embedded portable viewer (OHIF 3.11) for patients. No installation required on the patient's machine.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hospital Staff Web App                     │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Next.js 15  │◄──►│ Sanic Python │◄──►│  PACS / Horos │  │
│  │  (Frontend)  │    │  (Backend)   │    │  (DICOM SCP)  │  │
│  └──────────────┘    └──────┬───────┘    └───────────────┘  │
│                             │                                │
│                      ┌──────▼───────┐                       │
│                      │  CD Builder  │                       │
│                      │  (ISO/Burn)  │                       │
│                      └──────┬───────┘                       │
└─────────────────────┬───────┘───────────────────────────────┘
                      │
              ┌───────▼────────┐
              │   CD Contents  │
              ├────────────────┤
              │ STUDY/         │ ← DICOM files
              │ viewer/        │ ← OHIF 3.11 static build
              │ windows_view.exe│ ← Go launcher (Windows)
              │ macos_view     │ ← Go launcher (macOS)
              │ linux_view     │ ← Go launcher (Linux)
              │ autorun.inf    │ ← Windows autorun
              │ README.txt     │ ← Patient instructions
              └────────────────┘
```

## Components

### 1. Frontend (`/frontend`)
- **Next.js 15** with TypeScript and Tailwind CSS
- Patient search via DICOM C-FIND
- Study/Series browser with thumbnails
- ISO build progress + download to local PC for burning
- Material-UI components, Zustand state management

### 2. Backend (`/backend`)
- **Sanic Python** REST API
- DICOM Query/Retrieve (C-FIND, C-MOVE, C-GET) via pynetdicom
- ISO image creation using pycdlib (user downloads and burns locally)
- DICOM node (AE Title) management

### 3. Go Launcher (`/launcher`)
- Portable executables for Windows, macOS, Linux
- Starts embedded HTTP server on localhost
- Serves OHIF viewer static files
- Implements minimal DICOMweb (WADO-RS/QIDO-RS) from local STUDY/ folder
- Opens default browser automatically
- Zero installation required

### 4. CD Template (`/cd_template`)
- Directory structure template for burned CDs
- OHIF 3.11 static viewer build
- Patient-facing instructions

## How It Works

### For Hospital Staff:
1. Search for patient in PACS/Horos via the web app
2. Select studies and series to include
3. Click "Build ISO" — the server retrieves DICOM files, packages them with the viewer and launchers into an ISO
4. Download the ISO to your PC
5. Burn the ISO to CD/DVD using your OS tools (right-click → "Burn disc image" on Windows, Disk Utility on macOS)

### For Patients:
1. Insert CD into computer
2. Run the appropriate launcher:
   - **Windows**: Double-click `windows_view.exe` (or autorun)
   - **macOS**: Double-click `macos_view`
   - **Linux**: Run `./linux_view`
3. Browser opens with OHIF viewer showing their images
4. Close browser and launcher when done

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Go 1.21+
- CD/DVD burner (for actual burning)

### Setup
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py

# Frontend
cd frontend
npm install
npm run dev

# Build Launchers
cd launcher
make all
```

## Environment Variables

See `backend/.env.example` for configuration options including DICOM node settings and paths.

## License
See [LICENSE](./LICENSE) file.
