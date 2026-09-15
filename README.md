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

## Manual Android utilities

The browser includes Connect ADB, Refresh screenshot, Identify screen, Find button, Press matched button, Android Back/Home, and Open Azur Lane. These explicit manual commands work independently of the idle bot service. Stop controls the background bot; manual controls remain available. Controls are for trusted LAN clients; the listener address and existing Host/Origin/header checks are unchanged.

Manual tools require OpenCV and NumPy (`python3-opencv python3-numpy adb` on Debian, already present on this appliance). Development can use `python -m pip install numpy opencv-python`. The updater tests these dependencies before applying a release.

ADB uses `AUTOMATON_ADB_DEVICE` when configured. Otherwise, with Waydroid installed, it discovers the current IP from `waydroid status` and connects on port 5555. Other hosts require exactly one ready ADB device. Each manual request checks a fresh connection. Environment overrides belong in `~/.config/azurlane/automaton.env`.

Find shows best-match center coordinates, template size, score, threshold and pass/fail, including below-threshold results. Optional bounds are `x1,y1,x2,y2` at native resolution. Press captures and matches a fresh frame, taps once only when it passes, and displays the annotated pre-tap frame. Refresh screenshot to inspect the resulting UI. Requests are serialized; input commands are never automatically retried.

Button templates support `name.png`, `name_*.png`, and `name/*.png`. Existing battle variants are recognized. Missing-template buttons are disabled after Connect. The existing `main_menu.png` reference maps to HOME; `sleep.png` has no defined state and stays unused. Screen identification retains broad image similarity: scores are diagnostics, not calibrated probabilities. Templates and thresholds need tuning. Identification never triggers automatic input.

New utility facade operations: `inspectButton`, `connectADB`, `pressKey`, `launchGame`, `manualOptions`. Manual request logs are in `logs/control.log` and `journalctl --user -u azurlane-web`.

### Responsive previews and explicit manual taps

Capture uses Android's uncompressed RGBA screenshot format (12/16-byte headers), falling back to PNG for unsupported formats. Matching searches eight quarter-resolution candidates and refines them at native resolution; thresholds use native-resolution scores. This candidate search can differ from exhaustive matching on difficult images; `vision.best_template(..., fast=False)` remains available for comparison. Browser previews are 960-pixel-wide JPEGs; detection and tap coordinates remain full resolution. Warm connections use a readiness check rather than repeating discovery on every action.

A blocked press now says NO TAP and shows the score/threshold explicitly. After Find or a rejected press, **Tap preview location (manual)** lets the operator use the displayed match regardless of confidence. It never chooses a new match. The server-issued token expires in 30 seconds, is consumed before input, and is invalidated by another manual request or a device change. Check the displayed rectangle and ensure the game screen has not moved before using it. Refresh screenshot after a tap to inspect the outcome. The threshold-checked action remains separate.

Measured on this Debian host: raw capture about 0.35 seconds; complete battle Find requests about 1.06 seconds (previous capture plus matching alone was about 5.3 seconds). Actual timing depends on image/device load. Responses expose `elapsed_ms`.

## Browser template editor

Use **Capture for template**, drag a rectangle on the lossless screenshot, and adjust Left/Top/Right/Bottom for pixel-precise bounds. The crop preview and dimensions update immediately. Choose or create a target folder, choose Button, Screen area, or Number/OCR, then name the template and its variant. For example, the `battle` target can contain a `campaign_selector` screen and a `start` button. **Save template** saves a lossless PNG from the original server-side frame. Download saved PNG exports that same crop.

Templates are stored on the appliance under `local-templates/targets/<target>/<type>/<template>/<variant>.png`, with JSON capture metadata. Programs refer to one as `<target>/<template>`, such as `battle/campaign_selector`; the block type determines whether it searches buttons, screens, or numbers. This folder is ignored by Git and survives automatic updates without making the checkout dirty. It is local data: back it up separately or deliberately promote selected templates into the repository. Files with an existing variant name are not overwritten. Editor capture tokens expire after 15 minutes; at most three screenshots are retained in memory, and service restarts clear them.

Older unqualified templates remain available under Legacy entries. Saving a button crop enables/selects it in the manual controls. Cropped screen references compare only the saved area at the original framebuffer resolution; a resolution mismatch is skipped. Pick distinctive static graphics rather than changing numbers, animated backgrounds, or broad empty regions. Use full-screen selection when a complete screen reference is desired.

## Visual programs (Blockly)

Open `/programs` for the local, offline Blockly editor. Drag blocks under the single Start block, choose a program name, and Save. The main page also lists saved programs with Run, Favorite and Delete controls. Button, screen, number, and called-program fields are dropdowns populated from authored assets. Programs are JSON data interpreted by the bot service; no generated Python/JavaScript is executed. Available blocks include Press (boolean result), Wait, Wait for button or screen with timeout, If/Else, Repeat, bounded While, Call program, Return, variables/comparisons, numeric OCR, native-coordinate Tap, Log and End with error.

Press and Wait for button assign `last_result`. Call behaves like a function: the child program's Return value is stored in the variable named on the Call block and in `last_result`. A child without Return uses its final `last_result`. Variables are shared across calls within one run, and reset for the next run. Missing buttons return false; failed input commands stop the run rather than repeating taps. Read failures while waiting for buttons return false and can reconnect on the next poll. A missing/unreadable number fails the run; it is not guessed or treated as zero.

**Run saved** starts an explicit run in `azurlane-bot.service`. Editing/saving programs does not change that run: the called program library is snapshotted at start. Closing the browser does not stop a run. **Stop program** cancels at the next check; an in-flight ADB command can take its configured timeout. Stopping/restarting the bot service also ends the run. Crashed/interrupted runs are never automatically resumed or replayed. The default overall run limit is 12 hours, configurable up to 24 hours. Calls cannot recurse; loops and waits are bounded; each run has a 200,000-block step budget.

Programs, favorites, run requests, status and stop markers live in ignored `local-programs/` and `local-runtime/`. Saving keeps ten prior revisions per program under `local-programs/history/`. Delete removes the active program and preserves a recovery copy under `local-programs/deleted/`. Export/import JSON is available. Back up local authored data separately. Updates defer while a program/manual operation owns Android. Manual actions and template capture/save are excluded while a program runs to prevent competing input or changed templates.

**Dry run saved** uses simulated false button results, numeric reads of zero and shortened Wait blocks. It does not contact Android. It checks the executed branch, not every possible branch. Review all branches and test navigation in short runs before long unattended operation.

Examples in the editor:
- Safe demo: log, wait one second, log.
- Farm skeleton: intentionally begins with an error block until you author and test the navigation. It demonstrates press/branch/wait/return; it is not a completed 4-8 route.
- Oil supervisor: read `oil`; if greater than 3000, call saved `farm_4_8` four times, stopping if a child returns false. Save the child first. This only checks oil before the four calls; insert additional reads if each repetition needs a resource check.

### Named assets and numeric values

The template editor accepts a new button target name (for example `farm_start`) without editing Python enums. Existing named buttons remain compatible. Select **Number / OCR**, set a new target name such as `oil`, and crop just the current digits (exclude icons, maximum capacity and other labels). The latest numeric variant supplies the screen region. Numeric values use Tesseract with a digits whitelist and minimum confidence; compact K/M notation is not parsed. Resolution must match the saved crop.

The appliance has Tesseract 5.3.0 and English data extracted into `~/.local/share/azurlane/ocr`, using existing Debian native libraries. `bash scripts/install-ocr-user.sh` reproduces that user-local installation. System `tesseract` is used when available. No system/Waydroid services are reconfigured by OCR setup.

### Implementation boundaries

- `automation/programs.py`: validated data format, saved definitions, call graph checks and interpreter.
- `automation/program_worker.py`: bot service execution and utility-backed Android adapter.
- `automation/programs.js`: Blockly blocks, workspace serialization and translation to validated program data.
- `core/action_lock.py`: cross-process Android ownership.
- `core/numbers.py`: strict numeric crop OCR.
- `automation/vendor/blockly/`: pinned Blockly 13.3.0 with license; no runtime CDN dependency.

Tests use fake Android adapters for branching, calls, cancellation, dry-run isolation, limits and failed reads. A passing test suite does not certify any authored farming route or OCR crop against the game.
