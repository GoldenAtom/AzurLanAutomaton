from __future__ import annotations

import subprocess
import time
import struct
import ipaddress
import logging
import re
import shutil

import cv2
import numpy as np

import config


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


_device = None
log = logging.getLogger("adb")


def _host(*args):
    result = subprocess.run([config.ADB_PATH, *args], capture_output=True,
                            timeout=15, creationflags=_creation_flags())
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "ADB command failed")
    return result.stdout


def discover_device():
    if config.DEVICE:
        return config.DEVICE
    if shutil.which("waydroid"):
        result = subprocess.run(["waydroid", "status"], capture_output=True, text=True, timeout=10)
        match = re.search(r"IP address:\s*([0-9.]+)", result.stdout)
        if result.returncode == 0 and match:
            return str(ipaddress.IPv4Address(match.group(1))) + ":5555"
        raise RuntimeError("Waydroid has no usable IP. Start the Android session, then reconnect.")
    devices = [line.split()[0] for line in _host("devices").decode().splitlines()[1:]
               if len(line.split()) >= 2 and line.split()[1] == "device"]
    if len(devices) != 1:
        raise RuntimeError("Expected one ready ADB device; configure AUTOMATON_ADB_DEVICE explicitly.")
    return devices[0]


def device_name():
    return _device


def connect():
    global _device
    _device = None
    candidate = discover_device()
    if ":" in candidate:
        _host("connect", candidate)
    if _host("-s", candidate, "shell", "echo", "alive").strip() != b"alive":
        raise RuntimeError("ADB device failed its readiness check")
    _device = candidate
    log.info("Connected to %s", candidate)
    return True


def run_bytes(*args: str) -> bytes:
    if _device is None:
        connect()
    # Do not retry an input command: a lost reply must not duplicate a tap.
    return _host("-s", _device, *args)


def run_text(*args: str) -> str:
    return run_bytes(*args).decode(errors="replace").strip()


def is_alive() -> bool:
    try:
        if _device and run_text("shell", "echo", "alive") == "alive":
            return True
    except (OSError, RuntimeError, subprocess.SubprocessError):
        pass
    try:
        return connect()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        log.warning("ADB unavailable: %s", exc)
        return False


def decode_raw_screenshot(raw):
    if len(raw) < 12:
        raise ValueError("Short raw screenshot")
    width, height, format_id = struct.unpack_from("<3I", raw)
    if not (0 < width <= 16384 and 0 < height <= 16384) or format_id not in (1, 2):
        raise ValueError("Unsupported raw screenshot format")
    header = len(raw) - width * height * 4
    if header not in (12, 16):
        raise ValueError("Unexpected raw screenshot size")
    rgba = np.frombuffer(raw, np.uint8, offset=header).reshape(height, width, 4)
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)


def screenshot() -> np.ndarray:
    raw = run_bytes("exec-out", "screencap")
    try:
        return decode_raw_screenshot(raw)
    except ValueError:
        # Older/non-RGBA Android builds retain the portable PNG path.
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


def keyevent(key: str) -> None:
    codes = {"back": "4", "home": "3"}
    run_bytes("shell", "input", "keyevent", codes[key])
