from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

Region = tuple[int, int, int, int]


@dataclass(frozen=True)
class Match:
    score: float
    x: int
    y: int
    width: int
    height: int


def load_image(path: str | Path, unchanged: bool = True) -> np.ndarray:
    path = Path(path)
    mode = cv2.IMREAD_UNCHANGED if unchanged else cv2.IMREAD_COLOR
    image = cv2.imread(str(path), mode)

    if image is None:
        raise FileNotFoundError(path)

    return image


def crop(image: np.ndarray, region: Region) -> np.ndarray:
    x1, y1, x2, y2 = region
    return image[y1:y2, x1:x2]


def _template_and_mask(template: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    if template.ndim == 3 and template.shape[2] == 4:
        bgr = template[:, :, :3]
        alpha = template[:, :, 3]
        mask = cv2.merge((alpha, alpha, alpha))
        return bgr, mask

    return template, None


def find_template(
    screen: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.90,
    region: Region | None = None,
) -> Match | None:
    if region is not None:
        x1, y1, x2, y2 = region
        search = screen[y1:y2, x1:x2]
        offset_x, offset_y = x1, y1
    else:
        search = screen
        offset_x = offset_y = 0

    template_bgr, mask = _template_and_mask(template)

    if search.ndim == 2 and template_bgr.ndim == 3:
        search = cv2.cvtColor(search, cv2.COLOR_GRAY2BGR)
    elif search.ndim == 3 and template_bgr.ndim == 2:
        search = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)

    th, tw = template_bgr.shape[:2]
    sh, sw = search.shape[:2]

    if tw > sw or th > sh:
        return None

    if mask is not None:
        result = cv2.matchTemplate(search, template_bgr, cv2.TM_CCORR_NORMED, mask=mask)
    else:
        result = cv2.matchTemplate(search, template_bgr, cv2.TM_CCOEFF_NORMED)

    _, score, _, location = cv2.minMaxLoc(result)

    if not np.isfinite(score) or score < threshold:
        return None

    return Match(
        score=float(score),
        x=offset_x + location[0] + tw // 2,
        y=offset_y + location[1] + th // 2,
        width=tw,
        height=th,
    )


def image_similarity(a: np.ndarray, b: np.ndarray, size: tuple[int, int] = (320, 180)) -> float:
    """Return an inexpensive 0..1 visual similarity score.

    This is intentionally broad screen-state matching, not pixel-perfect comparison.
    Dynamic UI regions can later be excluded by the screen classifier.
    """
    a_small = cv2.resize(a, size, interpolation=cv2.INTER_AREA)
    b_small = cv2.resize(b, size, interpolation=cv2.INTER_AREA)

    if a_small.ndim == 3:
        a_small = cv2.cvtColor(a_small, cv2.COLOR_BGR2GRAY)
    if b_small.ndim == 3:
        b_small = cv2.cvtColor(b_small, cv2.COLOR_BGR2GRAY)

    a_small = cv2.GaussianBlur(a_small, (5, 5), 0)
    b_small = cv2.GaussianBlur(b_small, (5, 5), 0)

    diff = cv2.absdiff(a_small, b_small)
    return max(0.0, min(1.0, 1.0 - float(np.mean(diff)) / 255.0))


def best_similarity(image: np.ndarray, references: Iterable[np.ndarray]) -> float:
    scores = [image_similarity(image, reference) for reference in references]
    return max(scores, default=0.0)
