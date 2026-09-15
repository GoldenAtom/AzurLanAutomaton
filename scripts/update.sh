#!/usr/bin/env bash
set -Eeuo pipefail
cd "$HOME/AzurLanAutomaton"
mkdir -p local-runtime
exec 8>local-runtime/android.lock
flock -n 8 || { echo "Program or manual action active; update deferred"; exit 0; }
exec 9>"$HOME/.config/azurlane/update.lock"
flock -n 9 || exit 0
[[ $(git branch --show-current) == main ]] || { echo 'Refusing update: branch is not main'; exit 1; }
[[ -z $(git status --porcelain) ]] || { echo 'Refusing update: local changes exist'; exit 1; }
echo 'Fetching origin/main'
git fetch --prune origin main
old=$(git rev-parse HEAD)
new=$(git rev-parse origin/main)
[[ $old != "$new" ]] || { echo "Already current: $old"; exit 0; }
git merge-base --is-ancestor "$old" "$new" || { echo 'Refusing divergent history'; exit 1; }
stage=$(mktemp -d)
trap 'git worktree remove --force "$stage" >/dev/null 2>&1 || true' EXIT
git worktree add --detach "$stage" "$new"
(cd "$stage"; bash -n scripts/update.sh; bash -n scripts/install-user-services.sh; python3 -m compileall -q automation core AzureLaneAutomaton.py config.py utility.py; python3 -m unittest discover -s tests -v)
# Only fast-forward after validation. Never discard local modifications.
git merge --ff-only "$new"
for unit in systemd/azurlane-*; do install -m 644 "$unit" "$HOME/.config/systemd/user/"; done
systemctl --user daemon-reload
systemctl --user try-restart azurlane-bot.service azurlane-web.service azurlane-scrcpy.service
echo "Deployed $new (previous $old)"
