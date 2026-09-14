"""Native-pixel crop storage, separate from tracked deployment assets."""
import base64
import json
import re
import secrets
import threading
import time
import cv2
import config
import utility
from automation.manual import LOCK

FRAMES = {}
FRAME_LOCK = threading.Lock()
TTL = 900


def png(image):
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return data.tobytes()


def execute(action, payload):
    if action == "capture":
        if not LOCK.acquire(blocking=False):
            raise RuntimeError("Another Android action is running. Try again when it finishes.")
        try:
            device = utility.connectADB()
            frame = utility.getScreenshot()
        finally:
            LOCK.release()
        token = secrets.token_urlsafe(24)
        with FRAME_LOCK:
            now = time.monotonic()
            for old in list(FRAMES):
                if now-FRAMES[old][0] > TTL:
                    del FRAMES[old]
            while len(FRAMES) >= 3:
                del FRAMES[next(iter(FRAMES))]
            FRAMES[token] = (now, frame)
        return {"token": token, "width": frame.shape[1], "height": frame.shape[0], "device": device,
                "image": "data:image/png;base64,"+base64.b64encode(png(frame)).decode(),
                "buttons": [b.value for b in utility.Button],
                "screens": [s.value for s in utility.Screen if s != utility.Screen.UNKNOWN]}
    if action != "save":
        raise ValueError("Unknown template editor action")
    token = payload.get("token")
    kind, name, variant = payload.get("kind"), payload.get("name"), payload.get("variant")
    allowed = {"buttons": [b.value for b in utility.Button],
               "screens": [s.value for s in utility.Screen if s != utility.Screen.UNKNOWN]}
    if not isinstance(kind,str) or kind not in allowed or name not in allowed[kind]:
        raise ValueError("Choose a valid button or screen")
    if not isinstance(variant,str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}",variant):
        raise ValueError("Variant must be 1–48 lowercase letters, digits, underscores or hyphens")
    region = payload.get("region")
    if not isinstance(region,list) or len(region) != 4 or any(type(v) != int for v in region):
        raise ValueError("Crop requires four integer coordinates")
    with FRAME_LOCK:
        entry = FRAMES.get(token) if isinstance(token,str) else None
        if entry is None or time.monotonic()-entry[0] > TTL:
            raise ValueError("Screenshot expired or service updated. Capture a new screenshot.")
        frame=entry[1]
        x1,y1,x2,y2=region
        if not (0 <= x1 < x2 <= frame.shape[1] and 0 <= y1 < y2 <= frame.shape[0]):
            raise ValueError("Crop must be inside the screenshot")
        if x2-x1 < 4 or y2-y1 < 4:
            raise ValueError("Crop must be at least 4 by 4 pixels")
        image=frame[y1:y2,x1:x2].copy()
        directory=config.LOCAL_TEMPLATE_DIR/kind/name
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/(variant+".png")
        meta=path.with_suffix(".json")
        if path.exists() or meta.exists():
            raise ValueError("That variant already exists. Choose a new name; existing templates are preserved.")
        data=png(image)
        metadata={"region":region,"frame_size":[frame.shape[1],frame.shape[0]],"kind":kind,"name":name}
        # Write metadata before exposing the PNG to template discovery.
        with meta.open("x",encoding="utf-8") as output:
            json.dump(metadata,output)
        try:
            with path.open("xb") as output:
                output.write(data)
        except Exception:
            meta.unlink(missing_ok=True)
            raise
    return {"message":"Saved and active immediately. Custom variants replace bundled templates for this name.",
            "path":str(path.relative_to(config.BASE_DIR)),"width":x2-x1,"height":y2-y1,
            "image":"data:image/png;base64,"+base64.b64encode(data).decode(),"filename":path.name}
