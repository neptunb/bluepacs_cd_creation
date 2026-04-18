#!/usr/bin/env bash
# Copy the OHIF standalone viewer binaries from the neighbouring Viewers
# checkout into cd_template/standalone/ so the backend can burn them onto CDs.
#
# Layout expected at the source:
#   <repo-parent>/Viewers/standalone/dist/
#     ├── macos_view
#     ├── linux_view
#     ├── windows_view.exe
#     └── study/README.txt
#
# Override by exporting STANDALONE_SRC=/absolute/path before running.
#
# Usage:
#   ./scripts/sync_standalone.sh          # copy only files that changed
#   ./scripts/sync_standalone.sh --force  # always re-copy
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_PARENT="$(cd "$REPO_DIR/.." && pwd)"

SRC="${STANDALONE_SRC:-$REPO_PARENT/Viewers/standalone/dist}"
DEST="$REPO_DIR/cd_template/standalone"

force=0
for arg in "$@"; do
    case "$arg" in
        -f|--force) force=1 ;;
        -h|--help)
            sed -n '2,17p' "$0"
            exit 0
            ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [[ ! -d "$SRC" ]]; then
    echo "error: standalone source not found: $SRC" >&2
    echo "       build it first, e.g. 'make -C $REPO_PARENT/Viewers/standalone all'" >&2
    exit 1
fi

mkdir -p "$DEST/study"

copy_if_newer() {
    local src_file="$1"
    local dest_file="$2"
    if [[ ! -f "$src_file" ]]; then
        echo "error: missing expected file: $src_file" >&2
        exit 1
    fi
    if [[ $force -eq 1 || ! -f "$dest_file" || "$src_file" -nt "$dest_file" ]]; then
        cp -p "$src_file" "$dest_file"
        echo "  updated: ${dest_file#$REPO_DIR/}"
    else
        echo "  skipped (up to date): ${dest_file#$REPO_DIR/}"
    fi
}

echo "Syncing standalone viewers from: $SRC"
for bin in macos_view linux_view windows_view.exe; do
    copy_if_newer "$SRC/$bin" "$DEST/$bin"
done

chmod 755 "$DEST/macos_view" "$DEST/linux_view" 2>/dev/null || true

if [[ -f "$SRC/study/README.txt" ]]; then
    copy_if_newer "$SRC/study/README.txt" "$DEST/study/README.txt"
fi

echo "Done. STANDALONE_VIEWER_PATH defaults to: $DEST"
