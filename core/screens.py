from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json

import numpy as np

import config
from core import adb, assets, vision


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
    custom = sorted((config.LOCAL_TEMPLATE_DIR / "screens" / screen.value).glob("*.png"))
    if custom:
        return custom
    files: list[Path] = []

    single = config.SCREEN_TEMPLATE_DIR / f"{screen.value}.png"
    if single.exists():
        files.append(single)

    if screen is Screen.HOME:
        legacy = config.SCREEN_TEMPLATE_DIR / "main_menu.png"
        if legacy.exists():
            files.append(legacy)

    variants = config.SCREEN_TEMPLATE_DIR / screen.value
    if variants.is_dir():
        files.extend(sorted(variants.glob("*.png")))

    return files


def reference_files(reference) -> list[Path]:
    target,name=assets.split(reference)
    if target is not None:return assets.authored_files("screens",reference)
    try:return _reference_files(Screen(name))
    except ValueError:return sorted((config.LOCAL_TEMPLATE_DIR/"screens"/name).glob("*.png"))


def inspect_reference(reference,screen_image=None,threshold=config.DEFAULT_SCREEN_THRESHOLD):
    if screen_image is None:screen_image=adb.screenshot()
    matches=[]
    for path in reference_files(reference):
        image=vision.load_image(path,unchanged=False);search=screen_image
        if path.is_relative_to(config.LOCAL_TEMPLATE_DIR):
            metadata=json.loads(path.with_suffix(".json").read_text())
            if metadata["frame_size"] != [screen_image.shape[1],screen_image.shape[0]]:continue
            search=vision.crop(screen_image,tuple(metadata["region"]))
        matches.append((vision.image_similarity(search,image),path))
    if not matches:raise FileNotFoundError("No screen templates installed for "+reference)
    score,path=max(matches,key=lambda item:item[0])
    return {"score":score,"passed":score>=threshold,"reference":path}


def screen_visible(reference,screen_image=None,threshold=config.DEFAULT_SCREEN_THRESHOLD):
    return inspect_reference(reference,screen_image,threshold)["passed"]


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
            search_image = screen_image
            if path.is_relative_to(config.LOCAL_TEMPLATE_DIR):
                metadata = json.loads(path.with_suffix(".json").read_text())
                if metadata["frame_size"] != [screen_image.shape[1], screen_image.shape[0]]:
                    continue
                search_image = vision.crop(screen_image, tuple(metadata["region"]))
            score = vision.image_similarity(search_image, reference)

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
