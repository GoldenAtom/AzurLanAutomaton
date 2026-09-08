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

    path = template_path(button)
    if not path.exists():
        return None

    template = vision.load_image(path)
    return vision.find_template(screen, template, threshold=threshold, region=region)


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
