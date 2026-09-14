"""Serial manual requests use utility; the background worker stays idle."""
import base64
from dataclasses import asdict
import logging
import math
import threading
import time
import secrets
import cv2
import utility
from core.action_lock import android_owner

LOCK = threading.Lock()
PREVIEW = None
PREVIEW_TTL = 30
ACTIONS = {"connect", "screenshot", "identify", "find", "click", "back", "home", "launch", "tap_preview"}


def execute(action, payload):
    if action not in ACTIONS:
        raise ValueError("Unknown manual action")
    if not LOCK.acquire(blocking=False):
        raise RuntimeError("Another manual action is running. Wait for it to finish.")
    try:
        with android_owner():
            return _execute(action, payload)
    finally:
        LOCK.release()


def _execute(action, payload):
    global PREVIEW
    started = time.monotonic()
    threshold = payload.get("threshold", .93 if action in {"find", "click"} else .72)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be a number from 0 to 1")
    region = payload.get("region")
    if region is not None and (not isinstance(region, list) or len(region) != 4 or any(type(v) is not int for v in region)):
        raise ValueError("Region must contain four integer coordinates")
    button = str(payload.get("button", "redo_sortie")) if action in {"find", "click"} else None
    if action == "tap_preview":
        token = payload.get("preview_token")
        if not PREVIEW or not isinstance(token, str) or not secrets.compare_digest(token, PREVIEW["token"]):
            raise ValueError("No matching preview. Find the button again.")
        if time.monotonic() - PREVIEW["created"] > PREVIEW_TTL:
            PREVIEW = None
            raise ValueError("Preview expired after 30 seconds. Find the button again.")
        preview = PREVIEW
        PREVIEW = None  # consume before sending input; never replay a tap
        device = utility.connectADB()
        if device != preview["device"]:
            raise ValueError("Android device changed. Find the button again.")
        utility.tap(preview["x"], preview["y"])
        logging.getLogger("manual").info("Explicit preview tap at %s,%s", preview["x"], preview["y"])
        return {"action": action, "device": device, "clicked": True,
                "message": "Tap sent to the location you selected. Refresh screenshot to inspect the result.",
                "elapsed_ms": round((time.monotonic()-started)*1000)}
    PREVIEW = None
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
        result["message"] = (f"Match passed: {match.score:.4f} >= {threshold:.4f}." if match.passed
                             else f"NO TAP: score {match.score:.4f} is below threshold {threshold:.4f}.")
        if action == "find" or not match.passed:
            token = secrets.token_urlsafe(24)
            PREVIEW = {"token": token, "created": time.monotonic(), "device": device, "x": match.x, "y": match.y}
            result["preview_token"] = token
            result["preview_expires_seconds"] = PREVIEW_TTL
        if action == "click" and match.passed:
            utility.tap(match.x, match.y)
            result["clicked"] = True
            result["message"] = "Tap sent. Refresh screenshot to inspect the result."
            result["frame"] = "Detection frame BEFORE tap. Refresh screenshot to inspect the result."
        color = (70, 210, 90) if match.passed else (60, 150, 255)
        x, y = match.x - match.width // 2, match.y - match.height // 2
        cv2.rectangle(image, (x, y), (x + match.width, y + match.height), color, 3)
        cv2.putText(image, f"{button} {match.score:.3f} / {threshold:.3f}",
                    (max(0, x), max(25, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2)
    logging.getLogger("manual").info("%s", result)
    result["width"], result["height"] = image.shape[1], image.shape[0]
    preview_image = cv2.resize(image, (960, round(image.shape[0]*960/image.shape[1]))) if image.shape[1] > 960 else image
    ok, encoded = cv2.imencode(".jpg", preview_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("Could not encode screenshot")
    result["image"] = "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")
    result["elapsed_ms"] = round((time.monotonic()-started)*1000)
    return result
