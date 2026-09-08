from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

import config
from core import adb, vision


def timer_crop(screen: np.ndarray | None = None) -> np.ndarray:
    if screen is None:
        screen = adb.screenshot()
    return vision.crop(screen, config.BATTLE_TIMER_REGION)


def timer_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return vision.image_similarity(a, b, size=(160, 64))


@dataclass
class BattleTimerWatch:
    """Detect a timer that has stopped visually changing.

    This works before we implement OCR: if the cropped timer remains effectively
    identical for too long during a battle, the simulation is probably stalled.
    """

    stuck_after: float = 15.0
    similarity_threshold: float = 0.995

    def __post_init__(self) -> None:
        self._last: np.ndarray | None = None
        self._last_change = time.monotonic()

    def reset(self) -> None:
        self._last = None
        self._last_change = time.monotonic()

    def update(self, screen: np.ndarray | None = None) -> bool:
        current = timer_crop(screen)
        now = time.monotonic()

        if self._last is None:
            self._last = current
            self._last_change = now
            return False

        similarity = timer_similarity(self._last, current)
        if similarity < self.similarity_threshold:
            self._last_change = now

        self._last = current
        return (now - self._last_change) >= self.stuck_after


def get_timer(screen: np.ndarray | None = None) -> int | None:
    """Return remaining battle time in seconds once digit OCR is configured.

    Numeric timer parsing is intentionally left unimplemented for now. The
    watchdog above already lets us detect the battle-freeze case without OCR.
    """
    _ = screen
    return None
