#!/usr/bin/env bash
set -Eeuo pipefail
root="$HOME/.local/share/azurlane/ocr"
cache="$HOME/.cache/azurlane-ocr"
mkdir -p "$cache" "$root"
cd "$cache"
echo 'Downloading Debian Tesseract and English data into user storage'
apt-get download tesseract-ocr tesseract-ocr-eng
for archive in ./*.deb; do dpkg-deb -x "$archive" "$root"; done
TESSDATA_PREFIX="$root/usr/share/tesseract-ocr/5/tessdata" "$root/usr/bin/tesseract" --list-langs
echo 'OCR ready. Native libtesseract/liblept dependencies must be installed on the host.'
