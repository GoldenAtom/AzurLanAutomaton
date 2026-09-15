#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="${SCRCPY_VERSION:-4.1}"
SHA256="${SCRCPY_SHA256:-ad56ae8bfeedf41e824945c11dbf55fcb092b3e615b9b486f48a50e30d389635}"
ARCHIVE="scrcpy-linux-x86_64-v${VERSION}.tar.gz"
BASE="$HOME/.local/share/azurlane/scrcpy"
INSTALL="$BASE/scrcpy-linux-x86_64-v${VERSION}"
URL="https://github.com/Genymobile/scrcpy/releases/download/v${VERSION}/${ARCHIVE}"

mkdir -p "$BASE" "$HOME/.local/bin"
if [[ ! -x "$INSTALL/scrcpy" ]]; then
  curl -fL --retry 3 -o "$BASE/$ARCHIVE" "$URL"
  printf '%s  %s\n' "$SHA256" "$BASE/$ARCHIVE" | sha256sum -c -
  tar -xzf "$BASE/$ARCHIVE" -C "$BASE"
fi
ln -sfn "$INSTALL/scrcpy" "$HOME/.local/bin/scrcpy"
"$HOME/.local/bin/scrcpy" --version
echo "Installed official scrcpy v$VERSION for this user."
