"""Names and paths for user-authored target folders."""
from pathlib import Path
import re

import config

KINDS=("buttons","screens","numbers")
PATTERN=r"[a-z0-9][a-z0-9_-]{0,47}"


def slug(value,label="name"):
    if not isinstance(value,str) or not re.fullmatch(PATTERN,value):
        raise ValueError(f"Invalid {label}; use 1–48 lowercase letters, digits, hyphens or underscores")
    return value


def split(reference):
    if not isinstance(reference,str):
        raise ValueError("Invalid asset reference")
    parts=reference.split("/")
    if len(parts)==1:return None,slug(parts[0],"asset name")
    if len(parts)==2:return slug(parts[0],"target folder"),slug(parts[1],"asset name")
    raise ValueError("Asset reference must be target/name")


def reference(target,name):
    return slug(target,"target folder")+"/"+slug(name,"asset name")


def target_directory(kind,target,name=None):
    if kind not in KINDS:raise ValueError("Invalid template type")
    result=config.LOCAL_TEMPLATE_DIR/"targets"/slug(target,"target folder")/kind
    return result/slug(name,"asset name") if name is not None else result


def authored_files(kind,asset_reference):
    target,name=split(asset_reference)
    if target is None:return []
    return sorted(target_directory(kind,target,name).glob("*.png"))


def target_catalog():
    result={}
    root=config.LOCAL_TEMPLATE_DIR/"targets"
    if not root.is_dir():return result
    for target in sorted(p for p in root.iterdir() if p.is_dir() and re.fullmatch(PATTERN,p.name)):
        groups={}
        for kind in KINDS:
            base=target/kind
            groups[kind]=sorted(p.name for p in base.iterdir() if p.is_dir() and re.fullmatch(PATTERN,p.name) and any(p.glob("*.png"))) if base.is_dir() else []
        result[target.name]=groups
    return result


def target_options(kind):
    return [{"value":target+"/"+name,"label":target+" / "+name,"target":target,"name":name,
             "templates":[p.name for p in authored_files(kind,target+"/"+name)]}
            for target,groups in target_catalog().items() for name in groups[kind]]
