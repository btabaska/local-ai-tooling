#!/usr/bin/env bash
# fetch-trilium-mcp.sh (lai-16) — download the pinned OVDEN13/trilium-mcp static
# Go binary for the mcpo stdio bridge. The binary is a rebuildable artifact (like
# the model GGUFs in fetch-models.sh) so it is .gitignored; this script is its
# restore path. Bind-mounted into the mcpo container at /opt/trilium-mcp (ro).
set -euo pipefail
VERSION="v0.1.5"
ASSET="trilium-mcp-linux-amd64"
SHA256="5652773318b6800568660ce783f9e39c239b5004dd0a76a96fcb25df7368ce36"
DEST_DIR="$(cd "$(dirname "$0")/../docker/trilium-mcp" && pwd)"
DEST="$DEST_DIR/$ASSET"
URL="https://github.com/OVDEN13/trilium-mcp/releases/download/$VERSION/$ASSET"

mkdir -p "$DEST_DIR"
if [ -f "$DEST" ] && echo "$SHA256  $DEST" | sha256sum -c - >/dev/null 2>&1; then
  echo "trilium-mcp $VERSION already present + verified: $DEST"
  exit 0
fi
echo "Downloading trilium-mcp $VERSION ..."
curl -fsSL "$URL" -o "$DEST.tmp"
echo "$SHA256  $DEST.tmp" | sha256sum -c -
mv "$DEST.tmp" "$DEST"
chmod 0755 "$DEST"
echo "OK: $DEST ($(stat -c%s "$DEST") bytes, $VERSION)"
