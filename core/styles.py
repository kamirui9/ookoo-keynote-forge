"""内置发布会风格预设。description 会交给 LLM 扩写成完整的 style_guide。"""

STYLES = [
    {
        "id": "apple-minimal",
        "name": "极简黑场",
        "tagline": "纯黑背景 · 超大白字 · 产品聚光",
        "swatch": ["#000000", "#1d1d1f", "#f5f5f7"],
        "description": (
            "苹果发布会式极简风格：纯黑或极深灰背景，大面积留白，"
            "一页只讲一件事；超大号无衬线白色粗体标题，副文案为浅灰细体；"
            "产品以电影级棚拍质感居中呈现，单一柔和顶光与边缘轮廓光，"
            "偶尔点缀一抹产品本身的渐变色彩；整体克制、高级、安静。"
        ),
    },
    {
        "id": "cn-flagship",
        "name": "旗舰参数大字报",
        "tagline": "深色渐变 · 巨型数字 · 金属光泽",
        "swatch": ["#0b0b12", "#3a2a1a", "#e8c48a"],
        "description": (
            "国产旗舰手机发布会风格：深邃的黑到深蓝/深棕渐变背景，"
            "超大号醒目数字与关键参数（如 5000mAh、全球首发）作为视觉主体，"
            "数字带有香槟金或钛金属质感的渐变与微光；"
            "辅以精致的产品爆炸图、芯片特写或光线扫过的金属材质；"
            "排版强对比、气势感强、信息密度适中。"
        ),
    },
    {
        "id": "tech-future",
        "name": "未来科技",
        "tagline": "霓虹光效 · 粒子网格 · 赛博色调",
        "swatch": ["#05010f", "#6a00ff", "#00e5ff"],
        "description": (
            "未来科技发布会风格：近黑色深空背景，紫色与青色霓虹光效，"
            "细线网格、数据流、发光粒子与体积光营造空间纵深；"
            "标题为几何感强的无衬线粗体，带轻微外发光；"
            "产品或抽象科技元素悬浮于画面中央，充满速度感和未来感。"
        ),
    },
    {
        "id": "warm-lifestyle",
        "name": "温暖生活方式",
        "tagline": "浅色暖调 · 自然光 · 生活场景",
        "swatch": ["#f6f1ea", "#d9c3a5", "#3b3530"],
        "description": (
            "生活方式品牌发布会风格：米白、燕麦色等浅暖色调背景，"
            "柔和的自然窗光与真实生活场景（家居、户外、咖啡桌面），"
            "深棕色优雅无衬线标题，大量留白，杂志般的排版；"
            "产品融入场景之中，温暖、亲切、有质感。"
        ),
    },
]

STYLES_BY_ID = {s["id"]: s for s in STYLES}


def resolve_style(style_id: str | None, custom: str | None) -> str:
    """把预设和自定义描述合并成一段风格描述。"""
    parts = []
    if style_id and style_id in STYLES_BY_ID:
        parts.append(STYLES_BY_ID[style_id]["description"])
    if custom and custom.strip():
        parts.append("用户自定义风格要求（优先级最高）：" + custom.strip())
    return "\n".join(parts) or STYLES[0]["description"]
