# Standalone Viewer Binaries

This folder holds the **self-contained** OHIF viewer binaries that are burned
onto every CD the backend produces. Each binary bundles a Go web server, the
OHIF PWA, and Cornerstone's DICOM image loader, so patients don't need any
runtime (no Node, no Go, no OHIF install) on their side.

The binaries are intentionally **not committed to git** (they are ~900 MB in
total). Populate this folder before the backend can build OHIF ISOs.

## Expected layout

```
cd_template/standalone/
├── macos_view          universal / arm64 Mach-O
├── linux_view          linux/amd64 ELF
├── windows_view.exe    windows/amd64 PE
└── study/
    └── README.txt      patient-facing "drop DICOM files here" notice
```

For each platform the operator selects in the UI, the matching binary must
exist here (`macos_view`, `windows_view.exe`, and/or `linux_view`). Override
the path with `STANDALONE_VIEWER_PATH`.

## How to populate

Run the helper script from the repo root:

```bash
./scripts/sync_standalone.sh
```

The script copies the latest build from `../Viewers/standalone/dist/` (the
neighbouring `Viewers` repo checkout) into this folder. Re-run it whenever you
rebuild the standalone viewers:

```bash
# inside the Viewers checkout
make -C standalone all
# back in this repo
./scripts/sync_standalone.sh
```

You can also copy the four items above manually — any source is fine as long as
the layout matches.

## Why a separate viewer

The previous OHIF + Go launcher pipeline (`cd_template/viewer/` plus the
`launcher/` binary) rendered visible noise bands on some GPUs. The standalone
build ships a pinned OHIF + Cornerstone combination that does not exhibit that
regression, which is why it is now the only viewer the backend uses.
