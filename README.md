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
              │ DICOM/         │ ← DICOM files
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
- Optional **K-PACS Lite** second ISO: copies viewer binaries from [`cd_template/kpacs/`](cd_template/kpacs), copies the same retrieved `DICOM/` tree into a K-PACS staging folder, and runs **DCMTK `dcmmkdir`** to create a root `DICOMDIR` (install DCMTK and ensure `dcmmkdir` is on `PATH`; override template path with `KPACS_TEMPLATE_PATH` if needed)
- DICOM node (AE Title) management

### 3. Go Launcher (`/launcher`)
- Portable executables for Windows, macOS, Linux
- Starts embedded HTTP server on localhost
- Serves OHIF viewer static files
- Implements minimal DICOMweb (WADO-RS/QIDO-RS) from local `DICOM/` folder
- Opens default browser automatically
- Zero installation required

### 4. CD Template (`/cd_template`)
- Directory structure template for burned CDs
- OHIF 3.11 static viewer build
- K-PACS Lite Windows viewer and DLLs (no patient DICOM)
- Patient-facing instructions

## How It Works

### For Hospital Staff:
1. Search for patient in PACS/Horos via the web app
2. Select studies and series to include
3. Click "Build ISO" — the server retrieves DICOM files, packages them with the viewer and launchers into an ISO, and (when DCMTK is available) builds a second K-PACS-layout ISO
4. Download the OHIF ISO and, when offered, the K-PACS ISO to your PC
5. Burn the ISO to CD/DVD using your OS tools (right-click → "Burn disc image" on Windows, Disk Utility on macOS)

**macOS Finder note:** The **K-PACS** ISO is built **without Rock Ridge** so Finder usually shows `DICOM/`, `K-Pacs-Lite.exe`, etc. The **OHIF** ISO keeps **Rock Ridge** (Unix execute bits for `macos_view` / `linux_view`); on some macOS versions Finder can show that volume as empty even though the image is not (use an archiver such as Keka/The Unarchiver, or mount with `hdiutil attach -nomount path.iso` and `mount_cd9660` on the correct slice).

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
- **DCMTK** (`dcmmkdir` on `PATH`) if you want the K-PACS disc ISO when running the backend **outside** Docker (e.g. `brew install dcmtk` on macOS). The **backend Docker image** installs the `dcmtk` package so `dcmmkdir` is available inside the container.
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

------------
## Setup
#### How to find the LAN IP on macOS (Use one of them)
```
ifconfig | grep "inet " | grep -v 127.0.0.1   <-- First try this
ipconfig getifaddr en0
route get default | grep interface
```

Horos row to create at Locations
```
Field	         Value
AE Title	      BLUEPACS_CD
Host	         127.0.0.1 or your Mac LAN IP
Port	         11113
```
-----------
#### Define BLUEPACS_CD modalites and Remote PC's Pacs modalities
1. Define Remote DicomModality with the following definition for BLUEPACS_CD. Get BLUEPACS_CD PC's IP by using one of the above cli commands.
````
   "BLUEPACS_CD": ["BLUEPACS_CD", "192.168.65.1, 11113]
````
2. Add the following json data in dicom_nodes.json
```
   {
      "ae_title": "ORTHANC",
      "host": "192.168.1.32",   <-- Get this IP on the remote PC
      "port": 11112,
      "name": "PACS (Neptun @i13)"
   }
```