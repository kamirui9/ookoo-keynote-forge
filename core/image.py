"""调用 Qwen-Image 生成整页幻灯片图片。"""

import asyncio
import base64
import hashlib
import io
import re
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from . import config

NEGATIVE_PROMPT = (
    "低分辨率，模糊，文字错乱，乱码，错别字，多余的文字，水印，logo 变形，"
    "画面拥挤，廉价感，卡通，网页截图，PPT 模板边框"
)


def build_prompt(style_guide: str, slide: dict, with_reference: bool, feedback: str = "") -> str:
    lines = []
    if with_reference:
        lines.append(
            "参考图是同一场发布会的封面页。请只沿用参考图的配色、光影、材质、字体风格和整体视觉语言，"
            "不要沿用它的构图、主体位置和文字内容，生成一页全新的幻灯片。"
        )
    lines += [
        "一张 16:9 横版的科技新品发布会主舞台大屏幻灯片，整页设计，画面精致、具有高级感，像真实发布会的 Keynote 页面。",
        f"【统一视觉规范】{style_guide}",
        f"【画面】{slide['visual']}",
    ]
    text_parts = [f"主标题“{slide['title']}”"] if slide["title"] else []
    if slide.get("subtitle"):
        text_parts.append(f"副标题“{slide['subtitle']}”")
    if text_parts:
        lines.append(
            "【文字】画面上只出现以下文字，字形清晰准确、一字不差，排版大方："
            + "，".join(text_parts)
            + "。除此之外，只允许出现【画面】中明确写出的文字（如屏幕显示内容、数据标签），"
            "必须与描述完全一致；不要出现任何其他文字。"
        )
    else:
        lines.append("【文字】除【画面】中明确写出的文字外，不要出现任何文字。")
    if feedback.strip():
        lines.append(f"【修改要求】{feedback.strip()}")
    return "\n".join(lines)


def _image_to_data_url(path: Path, max_width: int = 1280) -> str:
    """把参考图压成 JPEG 再转 base64，避免请求体过大。"""
    img = Image.open(path).convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


async def generate_image(prompt: str, out_path: Path, reference: Path | None = None) -> None:
    if config.MOCK_MODE:
        await asyncio.sleep(1.5)
        _mock_image(prompt, out_path, reference is not None)
        return

    content = []
    if reference is not None:
        content.append({"image": _image_to_data_url(reference)})
    content.append({"text": prompt})

    body = {
        "model": config.IMAGE_MODEL,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": {
            "size": config.IMAGE_SIZE,
            "n": 1,
            "negative_prompt": NEGATIVE_PROMPT,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    url = f"{config.BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
    headers = {"Authorization": f"Bearer {config.API_KEY}"}

    async with httpx.AsyncClient(timeout=300) as client:
        for attempt in range(3):
            r = await client.post(url, headers=headers, json=body)
            if r.status_code == 200:
                break
            # 限流或服务端错误时退避重试
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"生图失败 {r.status_code}: {r.text[:300]}")

        data = r.json()
        try:
            image_url = data["output"]["choices"][0]["message"]["content"][0]["image"]
        except (KeyError, IndexError):
            raise RuntimeError(f"生图返回格式异常: {str(data)[:300]}")

        img = await client.get(image_url)
        img.raise_for_status()
        out_path.write_bytes(img.content)


def _mock_image(prompt: str, out_path: Path, with_reference: bool) -> None:
    w, h = 1664, 936
    hue = int(hashlib.md5(prompt.encode()).hexdigest()[:2], 16)
    img = Image.new("RGB", (w, h), (10, 10, 18))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=(int(10 + 40 * t), int(10 + hue * 0.2 * t), int(30 + 80 * t)))
    font = _load_font(64)
    small = _load_font(28)
    quoted = re.findall(r"“(.+?)”", prompt)
    draw.text((80, h // 2 - 80), quoted[0] if quoted else "（无文字）", fill=(245, 245, 247), font=font)
    if len(quoted) > 1:
        draw.text((80, h // 2 + 10), quoted[1], fill=(180, 180, 190), font=small)
    draw.text((80, h - 100), "MOCK" + (" · 图生图（参考封面）" if with_reference else " · 文生图"),
              fill=(160, 160, 170), font=small)
    img.save(out_path, "PNG")


def _load_font(size: int):
    for p in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()
