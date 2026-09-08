"""Public facade for the automation.

Main logic should import this module instead of reaching directly into ADB,
OpenCV, or the individual core modules.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import config
from core import adb, buttons, screens, timer, vision
from core.buttons import Button
from core.screens import Screen, ScreenMatch
from core.timer import BattleTimerWatch


def getScreenshot() -> np.ndarray:
    return adb.screenshot()


def tap(x: int | float, y: int | float) -> None:
    adb.tap(x, y)


def click(
    button: Button | str,
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_BUTTON_THRESHOLD,
    region: vision.Region | None = None,
) -> bool:
    return buttons.click_button(button, screen, threshold, region)


def exists(
    button: Button | str,
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_BUTTON_THRESHOLD,
    region: vision.Region | None = None,
) -> bool:
    return buttons.button_exists(button, screen, threshold, region)


def identifyScreen(
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_SCREEN_THRESHOLD,
) -> Screen:
    return screens.identify_screen(screen, threshold)


def identifyScreenDetails(
    screen: np.ndarray | None = None,
    threshold: float = config.DEFAULT_SCREEN_THRESHOLD,
) -> ScreenMatch:
    return screens.identify_screen_details(screen, threshold)


def getTimer(screen: np.ndarray | None = None) -> int | None:
    return timer.get_timer(screen)


def restartGame(delay: float = 2.0) -> None:
    adb.restart_app(delay=delay)


def adbAlive() -> bool:
    return adb.is_alive()


def saveDebug(image: np.ndarray, name: str = "unknown") -> Path:
    config.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = config.DEBUG_DIR / f"{name}_{timestamp}.png"
    cv2.imwrite(str(path), image)
    return path


# Snake-case aliases are also available for code that prefers PEP 8 naming.
get_screenshot = getScreenshot
identify_screen = identifyScreen
identify_screen_details = identifyScreenDetails
get_timer = getTimer
restart_game = restartGame
adb_alive = adbAlive
save_debug = saveDebug
