from __future__ import annotations

from enum import Enum
from pathlib import Path

import numpy as np

import config
from core import adb, vision


class Button(str, Enum):
    BATTLE = "battle"
    CONFIRM = "confirm"
    CONTINUE = "continue"
    SKIP = "skip"
    AUTO = "auto"
    PAUSE = "pause"
    REDO_SORTIE = "redo_sortie"


def _coerce_button(button: Button | str) -> Button:
    if isinstance(button, Button):
        return button
    return Button(str(button).lower())


def template_path(button: Button | str) -> Path:
    button = _coerce_button(button)
    return config.BUTTON_TEMPLATE_DIR / f"{button.value}.png"


def locate_button(
    button: Button | str,
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_BUTTON_THRESHOLD,
    region: vision.Region | None = None,
) -> vision.Match | None:
    if screen is None:
        screen = adb.screenshot()

    match = inspect_button(button, screen, threshold, region)
    return match if match is not None and match.passed else None


def template_files(button):
    name = _coerce_button(button).value
    files = list(config.BUTTON_TEMPLATE_DIR.glob(name + "_*.png"))
    direct = template_path(button)
    if direct.exists():
        files.append(direct)
    variants = config.BUTTON_TEMPLATE_DIR / name
    if variants.is_dir():
        files.extend(variants.glob("*.png"))
    return sorted(files)


def inspect_button(button, screen, threshold=config.DEFAULT_BUTTON_THRESHOLD, region=None):
    files = template_files(button)
    if not files:
        raise FileNotFoundError("No templates installed for " + _coerce_button(button).value)
    matches = [vision.best_template(screen, vision.load_image(path), threshold, region) for path in files]
    return max(matches, key=lambda match: match.score)


def button_exists(
    button: Button | str,
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_BUTTON_THRESHOLD,
    region: vision.Region | None = None,
) -> bool:
    return locate_button(button, screen, threshold, region) is not None


def click_button(
    button: Button | str,
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_BUTTON_THRESHOLD,
    region: vision.Region | None = None,
) -> bool:
    match = locate_button(button, screen, threshold, region)
    if match is None:
        return False

    adb.tap(match.x, match.y)
    return True
