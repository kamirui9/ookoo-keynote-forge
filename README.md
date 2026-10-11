# OokoO Keynote Forge · 发布会风格 PPT 生成器（PoC）

输入一句话主题，生成新品发布会风格的图片版 PPTX。每页都是由百炼 Qwen-Image 整页生成的 16:9 图片。

## 工作方式

1. **大纲**：`qwen3.8-max` 根据主题和风格生成统一视觉规范和逐页大纲（标题、副文案、画面描述），生成后可以在界面上编辑
2. **定风格**：先只生成封面，可以附修改意见重抽，满意后点“锁定风格”
3. **批量生成**：其余页面以封面作为参考图，用 `qwen-image-3.0` 图生图生成，保证整套风格一致；任意一页都能单独重抽
4. **导出**：每页一张全屏图片，打包成 `.pptx`，标题和副文案写在备注里

## 运行

```bash
cp .env.example .env    # 填入 DASHSCOPE_API_KEY
uv run python app.py    # 打开 http://127.0.0.1:8765
```

没有 API Key 时，可以用 Mock 模式体验完整流程（文案和图片都是占位内容）：

```bash
MOCK_MODE=1 uv run python app.py
```

## 配置（.env）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | — | 百炼 API Key（北京地域） |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com` | 可换成 `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com` |
| `TEXT_MODEL` | `qwen3.8-max` | 写大纲用的文本模型（推理模型，6 页大纲实测约 4 分钟） |
| `IMAGE_MODEL` | `qwen-image-3.0` | 生图模型，需要支持图生图（3.0 / 3.0-pro / 2.1 系列） |
| `IMAGE_SIZE` | `2048*1152` | 16:9 |
| `CONCURRENCY` | `3` | 同时生成的页数 |

## 目录

```
app.py            FastAPI 服务与接口
core/llm.py       大纲与视觉规范生成
core/image.py     生图提示词拼装与 Qwen-Image 调用
core/styles.py    内置风格预设
core/project.py   项目存储（projects/<id>/project.json + 图片）
core/export.py    PPTX 导出
static/           前端（原生 HTML/CSS/JS）
```

## 已知局限（PoC）

- 生图模型偶尔会写错字。标题越短越稳，出错时可以单页重抽
- 导出的 PPTX 里每页是一张图片，文字不能编辑
- 生成任务在内存中执行，服务重启后未完成的页面会被标记为失败，需要重新生成
