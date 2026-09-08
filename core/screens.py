from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np

import config
from core import adb, vision


class Screen(str, Enum):
    HOME = "home"
    MAP = "map"
    BATTLE = "battle"
    DIALOGUE = "dialogue"
    RESULT = "result"
    LOADING = "loading"
    DOCK = "dock"
    FORMATION = "formation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScreenMatch:
    screen: Screen
    score: float
    reference: Path | None = None


def _reference_files(screen: Screen) -> list[Path]:
    files: list[Path] = []

    single = config.SCREEN_TEMPLATE_DIR / f"{screen.value}.png"
    if single.exists():
        files.append(single)

    variants = config.SCREEN_TEMPLATE_DIR / screen.value
    if variants.is_dir():
        files.extend(sorted(variants.glob("*.png")))

    return files


def identify_screen_details(
    screen_image: np.ndarray | None = None,
    threshold: float = config.DEFAULT_SCREEN_THRESHOLD,
) -> ScreenMatch:
    if screen_image is None:
        screen_image = adb.screenshot()

    best = ScreenMatch(Screen.UNKNOWN, 0.0, None)

    for screen in Screen:
        if screen is Screen.UNKNOWN:
            continue

        for path in _reference_files(screen):
            reference = vision.load_image(path, unchanged=False)
            score = vision.image_similarity(screen_image, reference)

            if score > best.score:
                best = ScreenMatch(screen, score, path)

    if best.score < threshold:
        return ScreenMatch(Screen.UNKNOWN, best.score, best.reference)

    return best


def identify_screen(
    screen_image: np.ndarray | None = None,
    threshold: float = config.DEFAULT_SCREEN_THRESHOLD,
) -> Screen:
    return identify_screen_details(screen_image, threshold).screen
