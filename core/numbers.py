"""Read a strictly numeric value from an authored native-resolution crop."""
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import cv2
import config
from core import adb

def read_number(source):
    if not isinstance(source,str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}",source):
        raise ValueError("Invalid numeric source")
    candidates=list((config.LOCAL_TEMPLATE_DIR/"numbers"/source).glob("*.json"))
    if not candidates: raise ValueError("Create a Number crop named "+source+" in the template editor first")
    metadata=json.loads(max(candidates,key=lambda p:p.stat().st_mtime_ns).read_text())
    frame=adb.screenshot()
    if metadata["frame_size"] != [frame.shape[1],frame.shape[0]]:
        raise ValueError("Numeric crop resolution differs from Android")
    x1,y1,x2,y2=metadata["region"]
    image=cv2.cvtColor(frame[y1:y2,x1:x2],cv2.COLOR_BGR2GRAY)
    image=cv2.resize(image,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
    _,image=cv2.threshold(image,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    if image.mean()<127:image=255-image
    image=cv2.copyMakeBorder(image,10,10,10,10,cv2.BORDER_CONSTANT,value=255)
    executable=shutil.which("tesseract")
    env=os.environ.copy()
    if not executable:
        root=Path.home()/".local/share/azurlane/ocr/usr"
        executable=str(root/"bin/tesseract")
        env["TESSDATA_PREFIX"]=str(root/"share/tesseract-ocr/5/tessdata")
    ok,data=cv2.imencode(".png",image)
    if not ok:raise RuntimeError("OCR crop encoding failed")
    result=subprocess.run([executable,"stdin","stdout","--psm","7","-l","eng","-c","tessedit_char_whitelist=0123456789,","tsv"],input=data.tobytes(),capture_output=True,env=env,timeout=10)
    if result.returncode:raise RuntimeError("OCR failed: "+result.stderr.decode(errors="replace")[-300:])
    words=[row for row in csv.DictReader(io.StringIO(result.stdout.decode()),delimiter="\t") if row.get("text","").strip()]
    if len(words)!=1:raise ValueError("Number unreadable or ambiguous; adjust the saved crop")
    word=words[0];text=word["text"].strip();confidence=float(word["conf"])
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)",text) or confidence<60:
        raise ValueError("Number unreadable or low confidence: "+repr(text))
    return {"value":int(text.replace(",","")),"text":text,"confidence":confidence,"source":source}
