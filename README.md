# AzurLanAutomaton

BlueStacks/ADB automation experiment for Azur Lane.

## Architecture

`AzureLaneAutomaton.py` contains high-level behaviour only. It should normally call the public facade in `utility.py` rather than importing OpenCV or issuing ADB commands itself.

- `utility.py` - stable public API used by the main automaton
- `config.py` - user/environment configuration
- `core/adb.py` - BlueStacks ADB transport, screenshots, taps, app restart
- `core/vision.py` - image loading, transparency-aware template matching, similarity
- `core/buttons.py` - named button lookup/clicking
- `core/screens.py` - screen-state identification
- `core/timer.py` - battle timer crop/watchdog and future numeric timer parsing
- `templates/buttons/` - tightly cropped button templates such as `battle.png`
- `templates/screens/` - reference screenshots such as `home.png`
- `debug/` - runtime screenshots/logs; keep ignored by Git

## Public API examples

```python
import utility
from utility import Button, Screen

screen = utility.getScreenshot()
state = utility.identifyScreen(screen)

if state == Screen.HOME:
    utility.click(Button.BATTLE, screen)
```

Strings also work for buttons:

```python
utility.click("battle")
```

## Screen references

A screen may have either one reference image:

```text
templates/screens/home.png
```

or multiple variants:

```text
templates/screens/home/01.png
templates/screens/home/02.png
```

`identifyScreen()` checks all available known references and returns `Screen.UNKNOWN` if nothing reaches the configured confidence threshold.

## Transparent button templates

PNG alpha is preserved. `core/vision.py` uses the alpha channel as a template-matching mask, so transparent pixels do not contribute to matching.

## Debian idle service and browser controls

The default entry point now runs an idle lifecycle with bounded rotating logs. It does not capture screenshots, connect to Android, or tap anything. Existing Redo Sortie experimentation is preserved in `automation/redo_sortie.py` (explicit manual invocation: `python -m automation.redo_sortie`; this DOES interact with the game and requires NumPy/OpenCV).

Production checkout: `/home/tails/AzurLanAutomaton`, tracking `origin/main`.

```sh
git clone https://github.com/GoldenAtom/AzurLanAutomaton.git "$HOME/AzurLanAutomaton"
cd "$HOME/AzurLanAutomaton"
AUTOMATON_WEB_BIND=192.168.1.138 bash scripts/install-user-services.sh
```

Requires Debian Python 3, git, systemd user services, and util-linux (flock). No pip dependencies for idle mode. User lingering must be enabled for reboot startup; it is already enabled on the target host. Installer only manages this project's units; it backs up changed units and preserves existing environment configuration.

Browser: **http://192.168.1.138:8080**. Start, Stop, Restart, service status, deployed revision, service logs and update logs. LAN controls have no login; bind only to the trusted LAN address. Browser mutations require same-origin requests. No public exposure or changes to existing Caddy/noVNC configuration.

Settings: `~/.config/azurlane/automaton.env`. Change `AUTOMATON_WEB_BIND`/`AUTOMATON_WEB_PORT`, then `systemctl --user restart azurlane-web`. Defaults to loopback when installed without a bind address.

```sh
systemctl --user status azurlane-bot azurlane-web azurlane-update.timer
journalctl --user -u azurlane-bot -n 50
systemctl --user start azurlane-update.service  # check now
systemctl --user disable --now azurlane-update.timer  # suspend updates
```

The timer checks after boot and every five minutes. Updates fetch `origin/main`, refuse dirty/diverged checkouts, validate syntax and tests in an isolated git worktree, then fast-forward and refresh the units. Only running bot/web services restart: stopping the bot in the browser is preserved across updates. Enabled services start again on reboot. Network/check failures leave the existing version running and appear in update logs. Runtime failures after validation are reported by systemd; deployment does not automatically roll back. To roll back, disable updates, stop the bot, inspect git history, and deliberately select a known-good revision.

Logs rotate at 2 MB with three backups per runtime; systemd also captures logs in the host journal. Browser tails are bounded.

### Extension boundary

`automation/runtime.py:run(stop)` owns the lifecycle. Future high-level behaviour belongs behind that loop, using `utility.py`; transport and vision stay in `core/`. Service shutdown sets the stop event. Keep waits interruptible. Browser controls never directly invoke gameplay code.

ADB now defaults to `adb` from PATH. Set `AUTOMATON_ADB_PATH` for BlueStacks and `AUTOMATON_ADB_DEVICE` for a specific device. An empty device uses ADB's single-device selection (multiple devices fail rather than guessing). Discover/connect Waydroid before enabling any future game behaviour; idle mode does not depend on an internal IP. ADB commands have bounded timeouts.

Validation: `python3 -m unittest discover -s tests -v`.
