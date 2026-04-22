# BluePACS CD Creation

A web application for creating DICOM CD/DVDs with an embedded portable viewer (OHIF) for patients. No installation required on the patient's machine.

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
              │ study/         │ ← DICOM files (per StudyInstanceUID)
              │ windows_view.exe│ ← Standalone viewer (Windows)
              │ macos_view     │ ← Standalone viewer (macOS)
              │ linux_view     │ ← Standalone viewer (Linux)
              │ autorun.inf    │ ← Windows autorun
              │ README.txt     │ ← Patient instructions
              └────────────────┘
```

Each standalone launcher is a single self-contained binary (built from the
neighbouring `Viewers/standalone/` repo) that bundles a Go web server, the OHIF
PWA, and Cornerstone's DICOM image loader. On insert, it scans `./study/` and
opens the viewer in the default browser — no separate `viewer/` folder or
`launcher/` package is burned onto the disc.

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
- ISO image creation using pycdlib (user downloads and burns locally) — DICOM files are placed under `study/<StudyInstanceUID>/...` alongside the three standalone viewer binaries
- Optional **K-PACS Lite** second ISO: copies viewer binaries from [`cd_template/kpacs/`](cd_template/kpacs), copies the retrieved `DICOM/` tree into a K-PACS staging folder, and runs **DCMTK `dcmmkdir`** to create a root `DICOMDIR` (install DCMTK and ensure `dcmmkdir` is on `PATH`; override template path with `KPACS_TEMPLATE_PATH` if needed)
- DICOM node list is fetched from Ultramar's `dicom_modalities` table via
  `/assets/cd/cd_nodes_list.php` (CRUD is performed in the Uploader →
  *User Menu → Settings → Pacs Yerleri* page, guarded by
  `PRIVILEGES::P_CAN_SETTINGS_DICOM_MODALITIES`). Set `ULTRAMAR_NODES_URL`
  accordingly; when empty, `backend/dicom_nodes.sample.json` is used as a dev
  fallback. Only the local BLUEPACS_CD listener (`ae_title` + `port`) is kept
  in `backend/dicom_nodes.json`.

### 3. CD Template (`/cd_template`)
- [`cd_template/standalone/`](cd_template/standalone) — the three standalone viewer binaries (`macos_view`, `linux_view`, `windows_view.exe`) plus a `study/README.txt` placeholder. Populate with `./scripts/sync_standalone.sh` — see [cd_template/standalone/README.md](cd_template/standalone/README.md). The binaries are git-ignored.
- [`cd_template/kpacs/`](cd_template/kpacs) — K-PACS Lite Windows viewer and DLLs (no patient DICOM; optional second ISO only)

## How It Works

### For Hospital Staff:
1. Search for patient in PACS/Horos via the web app
2. Select studies and series to include
3. Click "Build ISO" — the server retrieves DICOM files, packages them with the viewer and launchers into an ISO, and (when DCMTK is available) builds a second K-PACS-layout ISO
4. Download the OHIF ISO and, when offered, the K-PACS ISO to your PC
5. Burn the ISO to CD/DVD using your OS tools (right-click → "Burn disc image" on Windows, Disk Utility on macOS)

**macOS Finder note:** Both **OHIF** and **K-PACS** disc ISOs are built **without Rock Ridge** (ISO9660 + Joliet only) so Finder usually lists `DICOM/`, launchers, and viewer files. On macOS/Linux, if `macos_view` or `linux_view` is not executable after copy, use `chmod +x` as in the on-disc `README.txt`.

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
- Populated [`cd_template/standalone/`](cd_template/standalone) (see below) — the OHIF ISO build will refuse to start without it
- **DCMTK** (`dcmmkdir` on `PATH`) if you want the K-PACS disc ISO when running the backend **outside** Docker (e.g. `brew install dcmtk` on macOS). The **backend Docker image** installs the `dcmtk` package so `dcmmkdir` is available inside the container.
- CD/DVD burner (for actual burning)

### Setup
```bash
# 1. Sync the standalone viewer binaries (expects ../Viewers/standalone/dist next door)
./scripts/sync_standalone.sh

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py

# 3. Frontend
cd ../frontend
npm install
npm run dev
```

### Rebuilding the standalone viewers
The binaries are produced by the neighbouring `Viewers/standalone/` repo:

```bash
# inside the Viewers checkout
make -C standalone all
# back in this repo — copy the fresh dist/ into cd_template/standalone/
./scripts/sync_standalone.sh
```

## Environment Variables

See `backend/.env.example` for configuration options including DICOM node settings and paths.

## Deployments

- **Development / single-box (stand-alone)**: `docker-compose.yml` at the
  repo root.
- **Integrated with the rest of the BluePACS stack** (rproxy, phpapi, pacs,
  uploader, …): the `cd-backend` and `cd-frontend` services live in the
  sibling [`Ultramar`](../Ultramar) repo — see
  [`Ultramar/docker-compose.yml`](../Ultramar/docker-compose.yml) (same file
  also defines optional `cd-caddy` for `https://cd.bluepacs.com` on the LAN;
  see [`Ultramar/Onsite-Readme.md`](../Ultramar/Onsite-Readme.md)). Production
  server layout uses `docker-compose-server.yml`.

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



---------------------
TO DOs:
1. 2GB download limit
2. STUDY zip  download for only infomed pacs. Download as 235/1
   infomed does not send total image count.
3. GE MR ve GE BT bağlantıları için BLUEPACS'ın karşılıklı AE Title tanıtılması. 