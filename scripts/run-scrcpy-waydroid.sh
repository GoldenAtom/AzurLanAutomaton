#!/usr/bin/env bash
set -Eeuo pipefail

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
SCRCPY="${AUTOMATON_SCRCPY_PATH:-$HOME/.local/bin/scrcpy}"
[[ -x "$SCRCPY" ]] || { echo "scrcpy is missing; run scripts/install-scrcpy-user.sh" >&2; exit 1; }

if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  socket="$(find "$XDG_RUNTIME_DIR" -maxdepth 1 -type s -name 'wayland-*' -printf '%T@ %f\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  [[ -n "$socket" ]] || { echo "The headless Wayland display is not ready" >&2; exit 1; }
  export WAYLAND_DISPLAY="$socket"
fi
export SDL_VIDEODRIVER=wayland

device="${AUTOMATON_ADB_DEVICE:-}"
if [[ -z "$device" ]]; then
  ip="$(waydroid status | sed -n 's/^IP address:[[:space:]]*//p' | head -n1)"
  [[ -n "$ip" ]] || { echo "Waydroid has no usable IP address" >&2; exit 1; }
  device="$ip:5555"
fi
adb connect "$device" >/dev/null

exec "$SCRCPY" \
  --serial="$device" \
  --no-audio \
  --keyboard=sdk \
  --mouse=sdk \
  --max-fps=30 \
  --max-size=1280 \
  --video-bit-rate=2M \
  --fullscreen \
  --window-title="Azur Lane · scrcpy"
