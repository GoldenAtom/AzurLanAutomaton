"""Serial manual requests use utility; the background worker stays idle."""
import base64
from dataclasses import asdict
import logging
import math
import threading
import cv2
import utility

LOCK = threading.Lock()
ACTIONS = {"connect", "screenshot", "identify", "find", "click", "back", "home", "launch"}


def execute(action, payload):
    if action not in ACTIONS:
        raise ValueError("Unknown manual action")
    if not LOCK.acquire(blocking=False):
        raise RuntimeError("Another manual action is running. Wait for it to finish.")
    try:
        return _execute(action, payload)
    finally:
        LOCK.release()


def _execute(action, payload):
    threshold = payload.get("threshold", .93 if action in {"find", "click"} else .72)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be a number from 0 to 1")
    region = payload.get("region")
    if region is not None and (not isinstance(region, list) or len(region) != 4 or any(type(v) is not int for v in region)):
        raise ValueError("Region must contain four integer coordinates")
    button = utility.Button(payload.get("button", "redo_sortie")) if action in {"find", "click"} else None
    device = utility.connectADB()
    result = {"action": action, "device": device}
    if action == "connect":
        return {**result, **utility.manualOptions(), "message": "ADB connected"}
    if action in {"back", "home"}:
        utility.pressKey(action)
    elif action == "launch":
        utility.launchGame()
    image = utility.getScreenshot()
    result["frame"] = "Captured after command" if action in {"back", "home", "launch"} else "Captured for this request"
    if action == "identify":
        match = utility.identifyScreenDetails(image, threshold)
        result.update(screen=match.screen.value, score=match.score, threshold=threshold,
                      reference=match.reference.name if match.reference else None)
    elif action in {"find", "click"}:
        match = utility.inspectButton(button, image, threshold, region)
        result["match"] = {**asdict(match), "passed": match.passed}
        result["clicked"] = False
        if action == "click" and match.passed:
            utility.tap(match.x, match.y)
            result["clicked"] = True
            result["frame"] = "Detection frame BEFORE tap. Refresh screenshot to inspect the result."
        color = (70, 210, 90) if match.passed else (60, 150, 255)
        x, y = match.x - match.width // 2, match.y - match.height // 2
        cv2.rectangle(image, (x, y), (x + match.width, y + match.height), color, 3)
        cv2.putText(image, f"{button.value} {match.score:.3f} / {threshold:.3f}",
                    (max(0, x), max(25, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2)
    logging.getLogger("manual").info("%s", result)
    result["width"], result["height"] = image.shape[1], image.shape[0]
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode screenshot")
    result["image"] = "data:image/png;base64," + base64.b64encode(encoded).decode("ascii")
    return result
