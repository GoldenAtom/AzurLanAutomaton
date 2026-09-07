import cv2
import numpy as np
import subprocess
import time
from pathlib import Path
from datetime import datetime


ADB = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
DEVICE = "127.0.0.1:5556"

DEBUG_DIR = Path("debug")
TEMPLATE_DIR = Path("templates")

DEBUG_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)


def adb_bytes(*args):
    cmd = [ADB, "-s", DEVICE, *args]

    return subprocess.check_output(
        cmd,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


def adb_text(*args):
    return adb_bytes(*args).decode(
        errors="replace"
    ).strip()


def screenshot():
    raw = adb_bytes(
        "exec-out",
        "screencap",
        "-p"
    )

    image = cv2.imdecode(
        np.frombuffer(raw, np.uint8),
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise RuntimeError(
            "ADB screenshot could not be decoded."
        )

    return image


def tap(x, y):
    adb_bytes(
        "shell",
        "input",
        "tap",
        str(int(x)),
        str(int(y))
    )


def save_debug(image, name="unknown"):
    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    path = DEBUG_DIR / f"{name}_{timestamp}.png"

    cv2.imwrite(str(path), image)

    return path


def load_template(name):
    path = TEMPLATE_DIR / f"{name}.png"

    image = cv2.imread(str(path))

    if image is None:
        raise FileNotFoundError(
            f"Missing template: {path}"
        )

    return image


def find_template(
    screen,
    template,
    threshold=0.90,
    region=None
):
    """
    region:
        (x1, y1, x2, y2)

    Returns:
        None
        or
        {
            "score": float,
            "x": int,
            "y": int
        }
    """

    if region:
        x1, y1, x2, y2 = region
        search = screen[y1:y2, x1:x2]
        offset_x = x1
        offset_y = y1
    else:
        search = screen
        offset_x = 0
        offset_y = 0

    th, tw = template.shape[:2]
    sh, sw = search.shape[:2]

    if tw > sw or th > sh:
        return None

    result = cv2.matchTemplate(
        search,
        template,
        cv2.TM_CCOEFF_NORMED
    )

    _, score, _, location = cv2.minMaxLoc(result)

    if score < threshold:
        return None

    x = offset_x + location[0] + tw // 2
    y = offset_y + location[1] + th // 2

    return {
        "score": float(score),
        "x": x,
        "y": y
    }


def click_template(
    screen,
    template,
    threshold=0.90,
    region=None
):
    match = find_template(
        screen,
        template,
        threshold,
        region
    )

    if match is None:
        return False

    print(
        f"Found at "
        f"({match['x']}, {match['y']}) "
        f"confidence={match['score']:.3f}"
    )

    tap(
        match["x"],
        match["y"]
    )

    return True


if __name__ == "__main__":

    print("Connecting to BlueStacks...")

    print(
        adb_text("shell", "wm", "size")
    )

    print("Capturing screenshot...")

    screen = screenshot()

    print(
        f"Screenshot: "
        f"{screen.shape[1]}x{screen.shape[0]}"
    )

    path = save_debug(
        screen,
        "startup"
    )

    print(
        f"Saved test image to: {path}"
    )

    print("ADB vision system working.")
