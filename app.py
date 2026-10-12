"""发布会风格 PPT 生成器 — 本地 Web 服务。运行：uv run python app.py"""

import asyncio
import base64
import secrets
from collections import defaultdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import config, project as store
from core.export import export_pptx
from core.image import build_prompt, generate_image
from core.llm import generate_outline
from core.styles import STYLES, resolve_style

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_gen_sem = asyncio.Semaphore(config.CONCURRENCY)
_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _reset_interrupted()
    yield


app = FastAPI(title="发布会 PPT 生成器", lifespan=lifespan)


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not (config.AUTH_USER and config.AUTH_PASSWORD) or request.url.path == "/healthz":
        return await call_next(request)
    user, password = "", ""
    scheme, _, encoded = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "basic":
        try:
            user, _, password = base64.b64decode(encoded).decode().partition(":")
        except (ValueError, UnicodeDecodeError):
            pass
    if secrets.compare_digest(user.encode(), config.AUTH_USER.encode()) & secrets.compare_digest(
        password.encode(), config.AUTH_PASSWORD.encode()
    ):
        return await call_next(request)
    return Response("需要登录", status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="OokoO Keynote Forge", charset="UTF-8"'})


@app.middleware("http")
async def no_cache_assets(request: Request, call_next):
    """页面、脚本和样式每次都要求浏览器确认是否有新版本，避免升级后仍运行旧脚本。
    /files/ 下的图片文件名带版本号、内容不会变，不加限制。"""
    response = await call_next(request)
    if not request.url.path.startswith("/files/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _reset_interrupted():
    """上次退出时没跑完的任务不会再继续，标记为失败以便重试。"""
    for item in store.list_projects():
        p = store.load(item["id"])
        changed = False
        for s in p["slides"]:
            if s["status"] in ("queued", "generating"):
                s.update(status="error", error="服务重启，任务中断，请重新生成")
                changed = True
        if changed:
            store.save(p)


def _require_api():
    if not config.MOCK_MODE and not config.API_KEY:
        raise HTTPException(400, "未配置 DASHSCOPE_API_KEY。请在 .env 中填写，或设置 MOCK_MODE=1 体验流程。")


def _load(pid: str) -> dict:
    try:
        return store.load(pid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "项目不存在")


async def _update_slide(pid: str, uid: str, **fields) -> dict | None:
    async with _locks[pid]:
        p = store.load(pid)
        for s in p["slides"]:
            if s["uid"] == uid:
                s.update(fields)
                store.save(p)
                return s
    return None


# ---------- 接口 ----------

class CreateReq(BaseModel):
    topic: str = Field(min_length=1)
    notes: str = ""
    style_id: str = "apple-minimal"
    custom_style: str = ""
    page_count: int = Field(10, ge=4, le=20)


class SlideIn(BaseModel):
    uid: str | None = None
    title: str = ""
    subtitle: str = ""
    visual: str = ""


class OutlineReq(BaseModel):
    style_guide: str
    slides: list[SlideIn]


class GenReq(BaseModel):
    feedback: str = ""


class LockReq(BaseModel):
    locked: bool


@app.get("/api/config")
def get_config():
    return {
        "mock": config.MOCK_MODE,
        "has_key": bool(config.API_KEY),
        "text_model": config.TEXT_MODEL,
        "image_model": config.IMAGE_MODEL,
    }


@app.get("/api/styles")
def get_styles():
    return STYLES


@app.get("/api/projects")
def get_projects():
    return store.list_projects()


@app.post("/api/projects")
async def create_project(req: CreateReq):
    _require_api()
    style_text = resolve_style(req.style_id, req.custom_style)
    try:
        outline = await generate_outline(req.topic, req.notes, style_text, req.page_count)
    except Exception as e:
        raise HTTPException(502, f"大纲生成失败：{e}")
    return store.new_project(req.topic, req.notes, req.style_id, req.custom_style,
                             style_text, req.page_count, outline)


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _load(pid)


@app.put("/api/projects/{pid}/outline")
async def update_outline(pid: str, req: OutlineReq):
    _load(pid)
    async with _locks[pid]:
        p = store.load(pid)
        old = {s["uid"]: s for s in p["slides"]}
        slides = []
        for i, s in enumerate(req.slides):
            data = s.model_dump()
            if s.uid and s.uid in old:
                merged = old[s.uid]
                merged.update({k: data[k] for k in ("title", "subtitle", "visual")})
                slides.append(merged)
            else:
                slides.append(store.new_slide(data))
        # 封面换了，已锁定的风格就不再成立
        if not slides or not old or slides[0]["uid"] != p["slides"][0]["uid"]:
            p["cover_locked"] = False
        p["slides"] = slides
        p["style_guide"] = req.style_guide
        store.save(p)
        return p


@app.post("/api/projects/{pid}/lock")
async def lock_cover(pid: str, req: LockReq):
    _load(pid)
    async with _locks[pid]:
        p = store.load(pid)
        if req.locked and not p["slides"][0].get("image"):
            raise HTTPException(400, "请先生成封面")
        p["cover_locked"] = req.locked
        store.save(p)
        return p


@app.post("/api/projects/{pid}/slides/{uid}/generate")
async def generate_slide(pid: str, uid: str, req: GenReq):
    _require_api()
    p = _load(pid)
    idx = next((i for i, s in enumerate(p["slides"]) if s["uid"] == uid), None)
    if idx is None:
        raise HTTPException(404, "页面不存在")
    if idx > 0 and not p["cover_locked"]:
        raise HTTPException(400, "请先生成并锁定封面风格")
    if idx == 0:
        async with _locks[pid]:
            q = store.load(pid)
            q["cover_locked"] = False
            store.save(q)
    slide = await _update_slide(pid, uid, status="queued", error=None)
    _schedule(pid, uid, req.feedback)
    return slide


@app.post("/api/projects/{pid}/generate-all")
async def generate_all(pid: str):
    _require_api()
    p = _load(pid)
    if not p["cover_locked"]:
        raise HTTPException(400, "请先生成并锁定封面风格")
    queued = 0
    for s in p["slides"][1:]:
        if s["status"] in ("idle", "error"):
            await _update_slide(pid, s["uid"], status="queued", error=None)
            _schedule(pid, s["uid"], "")
            queued += 1
    return {"queued": queued}


@app.get("/api/projects/{pid}/export")
def export(pid: str):
    p = _load(pid)
    if not any(s.get("image") for s in p["slides"]):
        raise HTTPException(400, "还没有生成任何页面")
    data = export_pptx(p, store.project_dir(pid))
    filename = f"launch-{pid}.pptx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/files/{pid}/{name}")
def get_file(pid: str, name: str):
    d = store.project_dir(pid)
    f = (d / name).resolve()
    if not f.is_relative_to(d.resolve()) or not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


# ---------- 后台生成 ----------

def _schedule(pid: str, uid: str, feedback: str):
    t = asyncio.create_task(_run_generation(pid, uid, feedback))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


async def _run_generation(pid: str, uid: str, feedback: str):
    async with _gen_sem:
        p = store.load(pid)
        slides = p["slides"]
        idx = next((i for i, s in enumerate(slides) if s["uid"] == uid), None)
        if idx is None:
            return
        slide = slides[idx]
        await _update_slide(pid, uid, status="generating")

        pdir = store.project_dir(pid)
        reference = None
        if idx > 0:
            cover = slides[0].get("image")
            reference = pdir / cover if cover else None

        version = slide["version"] + 1
        name = f"{uid}_v{version}.png"
        prompt = build_prompt(p["style_guide"], slide, reference is not None, feedback)
        try:
            await generate_image(prompt, pdir / name, reference)
        except Exception as e:
            await _update_slide(pid, uid, status="error", error=str(e))
            return
        await _update_slide(pid, uid, status="done", image=name, version=version,
                            prompt=prompt, error=None)


app.mount("/", StaticFiles(directory=config.ROOT / "static", html=True), name="static")


if __name__ == "__main__":
    mode = "MOCK 模式" if config.MOCK_MODE else ("已配置 API Key" if config.API_KEY else "⚠ 未配置 API Key")
    auth = "已启用登录" if config.AUTH_USER and config.AUTH_PASSWORD else "未启用登录"
    print(f"发布会 PPT 生成器：http://{config.HOST}:{config.PORT} （{mode}，{auth}）")
    # 生成任务在进程内存中排队，只能单进程运行，不要开多个 worker
    uvicorn.run(app, host=config.HOST, port=config.PORT)
