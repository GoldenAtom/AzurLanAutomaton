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
    threshold: float = 0.90

    @property
    def passed(self) -> bool:
        return self.score >= self.threshold


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


def best_template(
    screen: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.90,
    region: Region | None = None,
    fast: bool = True,
) -> Match | None:
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between 0 and 1")
    if region is not None:
        x1, y1, x2, y2 = region
        if not (0 <= x1 < x2 <= screen.shape[1] and 0 <= y1 < y2 <= screen.shape[0]):
            raise ValueError("Region must lie inside the screenshot")
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
        raise ValueError("Template is larger than the search region")

    if fast and min(tw, th) >= 80 and sw > tw * 2 and sh > th * 2:
        # Locate eight coarse candidates, then score each at original resolution.
        # Threshold decisions always use the original pixels, never preview scores.
        scale = 4
        small_template = cv2.resize(template_bgr, (tw // scale, th // scale), interpolation=cv2.INTER_AREA)
        small_search = cv2.resize(search, (sw // scale, sh // scale), interpolation=cv2.INTER_AREA)
        small_mask = None if mask is None else cv2.resize(mask, (tw // scale, th // scale), interpolation=cv2.INTER_NEAREST)
        method = cv2.TM_CCORR_NORMED if mask is not None else cv2.TM_CCOEFF_NORMED
        scores = cv2.matchTemplate(small_search, small_template, method, mask=small_mask)
        scores = np.where(np.isfinite(scores), scores, -2.0)
        candidates = []
        for _ in range(8):
            _, value, _, (cx, cy) = cv2.minMaxLoc(scores)
            if value <= -2:
                break
            px, py = cx * scale, cy * scale
            margin = 12
            left, top = max(0, px-margin), max(0, py-margin)
            right, bottom = min(sw, px+tw+margin), min(sh, py+th+margin)
            candidate = best_template(search, template, threshold, (left, top, right, bottom), fast=False)
            candidates.append(Match(candidate.score, candidate.x+offset_x, candidate.y+offset_y, tw, th, threshold))
            dx, dy = max(1, tw//scale//2), max(1, th//scale//2)
            scores[max(0,cy-dy):cy+dy+1, max(0,cx-dx):cx+dx+1] = -2
        if candidates:
            return max(candidates, key=lambda candidate: candidate.score)

    if mask is not None and not np.any(mask):
        raise ValueError("Template is entirely transparent")
    if mask is not None:
        result = cv2.matchTemplate(search, template_bgr, cv2.TM_CCORR_NORMED, mask=mask)
    else:
        # Constant templates produce meaningless perfect CCOEFF scores.
        if np.all(np.std(template_bgr.astype(float), axis=(0, 1)) < 1e-6):
            raise ValueError("Template has no visual variation")
        result = cv2.matchTemplate(search, template_bgr, cv2.TM_CCOEFF_NORMED)

    finite = np.isfinite(result)
    if not np.any(finite):
        raise ValueError("No finite template scores")
    result = np.where(finite, result, -1.0)
    _, score, _, location = cv2.minMaxLoc(result)

    return Match(
        score=float(score),
        x=offset_x + location[0] + tw // 2,
        y=offset_y + location[1] + th // 2,
        width=tw,
        height=th,
        threshold=threshold,
    )


def find_template(screen, template, threshold=0.90, region=None):
    """Compatibility API: only return accepted matches."""
    match = best_template(screen, template, threshold, region)
    return match if match.passed else None


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
