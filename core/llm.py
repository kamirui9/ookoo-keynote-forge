"""用 Qwen 文本模型生成发布会大纲与统一视觉风格说明。"""

import json

import httpx

from . import config

SLIDE_TYPES = {
    "cover": "封面：产品名 + 一句 slogan，主视觉是产品英雄图",
    "hook": "开场悬念：一句引发好奇的话，画面极简",
    "feature": "核心卖点：一个卖点标题 + 一句解释，配合特写画面",
    "spec": "参数大字报：一个巨大的数字或参数作为视觉主体",
    "compare": "对比：新旧/竞品的直观对比画面",
    "scene": "使用场景：产品在真实生活场景中",
    "price": "价格与发售：价格、发售时间",
    "ending": "结尾：品牌 slogan 或 Thank you",
}

OUTLINE_SYSTEM = """你是顶级科技公司发布会的创意总监，同时精通 AI 生图提示词。
你要为一场新品发布会设计幻灯片。每一页都会用文生图模型整页生成为一张 16:9 图片，
所以页面上的文字必须极短、醒目（生图模型渲染长文字容易出错）。

严格输出 JSON，结构如下：
{
  "style_guide": "统一视觉规范（150-300字）：背景、主色与点缀色、光影、材质、字体气质（如粗体无衬线）、排版原则。会被拼接到每一页的生图提示词里，保证全套风格一致。",
  "slides": [
    {
      "type": "页面类型，取值见下",
      "title": "主标题，不超过12个字（数字和英文型号可以）",
      "subtitle": "副文案，不超过20个字，可为空字符串",
      "visual": "这一页的画面描述（60-150字）：主体是什么、构图、镜头、文字摆放位置。不要重复写全局风格。"
    }
  ]
}

页面类型：
""" + "\n".join(f"- {k}：{v}" for k, v in SLIDE_TYPES.items()) + """

规则：
- 第一页必须是 cover，最后一页必须是 ending。
- 节奏要有发布会的起伏：悬念 → 卖点 → 参数震撼 → 场景 → 价格 → 收尾。
- 用户没提供的具体参数可以合理虚构，但要可信。
- 所有文字使用简体中文（型号、单位、品牌英文名除外）。"""


async def _chat(messages: list[dict]) -> str:
    url = f"{config.BASE_URL}/compatible-mode/v1/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {config.API_KEY}"},
            json={
                "model": config.TEXT_MODEL,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.8,
            },
        )
    if r.status_code != 200:
        raise RuntimeError(f"文本模型调用失败 {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


async def generate_outline(topic: str, notes: str, style_text: str, page_count: int) -> dict:
    if config.MOCK_MODE:
        return _mock_outline(topic, page_count)

    user = (
        f"发布会主题：{topic}\n"
        f"补充说明：{notes or '无'}\n"
        f"页数：{page_count} 页\n"
        f"视觉风格方向：\n{style_text}\n\n"
        "请据此输出 style_guide 和 slides。"
    )
    raw = await _chat([
        {"role": "system", "content": OUTLINE_SYSTEM},
        {"role": "user", "content": user},
    ])
    data = json.loads(raw)
    slides = [
        {
            "type": s.get("type", "feature") if s.get("type") in SLIDE_TYPES else "feature",
            "title": str(s.get("title", "")).strip(),
            "subtitle": str(s.get("subtitle", "")).strip(),
            "visual": str(s.get("visual", "")).strip(),
        }
        for s in data.get("slides", [])
    ]
    if not slides:
        raise RuntimeError("文本模型没有返回任何页面")
    return {"style_guide": str(data.get("style_guide", "")).strip(), "slides": slides}


def _mock_outline(topic: str, page_count: int) -> dict:
    types = ["cover", "hook", "feature", "spec", "feature", "compare", "scene", "spec", "price", "ending"]
    if page_count < len(types):
        types = types[: page_count - 1] + ["ending"]
    else:
        types = types[:-1] + ["feature"] * (page_count - len(types)) + ["ending"]
    slides = [
        {
            "type": t,
            "title": topic[:12] if t == "cover" else f"{t.upper()} 第{i + 1}页",
            "subtitle": "这是 Mock 模式下的占位文案",
            "visual": f"{SLIDE_TYPES[t]}（Mock）",
        }
        for i, t in enumerate(types)
    ]
    return {"style_guide": "Mock 模式：深色背景，白色粗体大字。", "slides": slides}
