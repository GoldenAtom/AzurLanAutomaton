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
