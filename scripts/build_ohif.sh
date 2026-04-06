#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VIEWER_DIR="$PROJECT_DIR/cd_template/viewer"

OHIF_VERSION="3.11.0"
OHIF_REPO="https://github.com/OHIF/Viewers.git"

TEMP_DIR=$(mktemp -d)
echo "Building OHIF Viewer v${OHIF_VERSION}..."
echo "Working directory: $TEMP_DIR"

git clone --branch "v${OHIF_VERSION}" --depth 1 "$OHIF_REPO" "$TEMP_DIR/ohif"
cd "$TEMP_DIR/ohif"

# Custom app config for local DICOMweb mode
cat > platform/app/.env <<'EOF'
APP_CONFIG=config/local_static.js
EOF

mkdir -p platform/app/public/config
cat > platform/app/public/config/local_static.js <<'JSEOF'
window.config = {
  routerBasename: '/',
  showStudyList: true,
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'local',
      configuration: {
        friendlyName: 'Local DICOM Files',
        name: 'local',
        wadoUriRoot: '/dicomweb',
        qidoRoot: '/dicomweb',
        wadoRoot: '/dicomweb',
        qidoSupportsIncludeField: false,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: false,
        supportsWildcard: false,
      },
    },
  ],
  defaultDataSourceName: 'local',
};
JSEOF

yarn install --frozen-lockfile
QUICK_BUILD=true yarn run build

rm -rf "$VIEWER_DIR"/*
cp -r platform/app/dist/* "$VIEWER_DIR/"

rm -rf "$TEMP_DIR"

echo "OHIF Viewer built and copied to $VIEWER_DIR"
echo "Done!"
