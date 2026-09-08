from __future__ import annotations

import subprocess
import time

import cv2
import numpy as np

import config


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_bytes(*args: str) -> bytes:
    cmd = [config.ADB_PATH, "-s", config.DEVICE, *args]
    return subprocess.check_output(cmd, creationflags=_creation_flags())


def run_text(*args: str) -> str:
    return run_bytes(*args).decode(errors="replace").strip()


def is_alive() -> bool:
    try:
        return run_text("shell", "echo", "alive") == "alive"
    except (OSError, subprocess.SubprocessError):
        return False


def screenshot() -> np.ndarray:
    raw = run_bytes("exec-out", "screencap", "-p")
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)

    if image is None:
        raise RuntimeError("ADB screenshot could not be decoded.")

    return image


def tap(x: int | float, y: int | float) -> None:
    run_bytes("shell", "input", "tap", str(int(x)), str(int(y)))


def force_stop(package_name: str = config.PACKAGE_NAME) -> None:
    run_bytes("shell", "am", "force-stop", package_name)


def launch(package_name: str = config.PACKAGE_NAME) -> None:
    run_bytes(
        "shell",
        "monkey",
        "-p",
        package_name,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    )


def restart_app(package_name: str = config.PACKAGE_NAME, delay: float = 2.0) -> None:
    force_stop(package_name)
    time.sleep(delay)
    launch(package_name)
