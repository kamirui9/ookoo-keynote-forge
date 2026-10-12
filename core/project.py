"""项目数据的读写。每个项目一个目录：project.json + 每页图片。"""

import json
import time
import uuid
from pathlib import Path

from .config import PROJECTS_DIR


def project_dir(pid: str) -> Path:
    d = PROJECTS_DIR / pid
    if not d.resolve().is_relative_to(PROJECTS_DIR.resolve()):
        raise ValueError("非法项目 ID")
    return d


def new_project(topic: str, notes: str, style_id: str, custom_style: str,
                style_text: str, page_count: int, outline: dict) -> dict:
    pid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    project = {
        "id": pid,
        "topic": topic,
        "notes": notes,
        "style_id": style_id,
        "custom_style": custom_style,
        "style_text": style_text,
        "page_count": page_count,
        "style_guide": outline["style_guide"],
        "cover_locked": False,
        "slides": [new_slide(s) for s in outline["slides"]],
    }
    project_dir(pid).mkdir(parents=True)
    save(project)
    return project


def new_slide(s: dict) -> dict:
    return {
        "uid": uuid.uuid4().hex[:8],
        "title": s.get("title", ""),
        "subtitle": s.get("subtitle", ""),
        "visual": s.get("visual", ""),
        "status": "idle",  # idle | queued | generating | done | error
        "image": None,
        "version": 0,
        "error": None,
    }


def load(pid: str) -> dict:
    return json.loads((project_dir(pid) / "project.json").read_text("utf-8"))


def save(project: dict) -> None:
    d = project_dir(project["id"])
    tmp = d / "project.json.tmp"
    tmp.write_text(json.dumps(project, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(d / "project.json")


def list_projects() -> list[dict]:
    items = []
    for d in sorted(PROJECTS_DIR.iterdir(), reverse=True):
        f = d / "project.json"
        if f.exists():
            p = json.loads(f.read_text("utf-8"))
            items.append({"id": p["id"], "topic": p["topic"], "pages": len(p["slides"])})
    return items
