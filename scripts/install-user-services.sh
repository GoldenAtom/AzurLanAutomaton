#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/AzurLanAutomaton"
python3 -m unittest discover -s tests -v
if [[ ! -x "$HOME/.local/bin/scrcpy" ]]; then
  bash scripts/install-scrcpy-user.sh
fi
mkdir -p "$HOME/.config/systemd/user" "$HOME/.config/azurlane"
if [[ ! -e "$HOME/.config/azurlane/automaton.env" ]]; then
  printf 'AUTOMATON_WEB_BIND=%s\nAUTOMATON_WEB_PORT=8080\n' "${AUTOMATON_WEB_BIND:-127.0.0.1}" > "$HOME/.config/azurlane/automaton.env"
fi
for unit in systemd/azurlane-*; do
  target="$HOME/.config/systemd/user/$(basename "$unit")"
  if [[ -f "$target" ]] && ! cmp -s "$unit" "$target"; then
    cp -p "$target" "$target.backup.$(date +%s)"
  fi
  install -m 644 "$unit" "$target"
done
systemctl --user daemon-reload
systemctl --user enable --now azurlane-bot.service azurlane-web.service azurlane-scrcpy.service azurlane-update.timer
echo 'Installed. Boot persistence requires loginctl enable-linger for this user.'
