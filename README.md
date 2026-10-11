# OokoO Keynote Forge · 发布会风格 PPT 生成器（PoC）

输入一句话主题，生成新品发布会风格的图片版 PPTX。每页都是由百炼 Qwen-Image 整页生成的 16:9 图片。

## 工作方式

1. **大纲**：`qwen-plus` 根据主题和风格生成统一视觉规范和逐页大纲（标题、副文案、画面描述），生成后可以在界面上编辑
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
| `TEXT_MODEL` | `qwen-plus` | 写大纲用的文本模型（8 页大纲实测约 80 秒）。可换成推理模型 `qwen3.8-max`，质量相近但约慢 3～4 倍 |
| `IMAGE_MODEL` | `qwen-image-3.0` | 生图模型，需要支持图生图（3.0 / 3.0-pro / 2.1 系列） |
| `IMAGE_SIZE` | `2048*1152` | 16:9 |
| `CONCURRENCY` | `3` | 同时生成的页数 |
| `AUTH_USER` / `AUTH_PASSWORD` | 空 | 两项都填写时启用登录（HTTP Basic）。部署到服务器时强烈建议填写 |

## 用 Docker Compose 部署到服务器

服务器需要：Docker 和 Docker Compose v2，并且能访问外网的 `dashscope.aliyuncs.com`，以及百炼返回图片所用的阿里云 OSS 域名（`*.aliyuncs.com`）。

```bash
git clone https://github.com/kamirui9/ookoo-keynote-forge.git
cd ookoo-keynote-forge
cp .env.example .env
```

编辑 `.env`：至少填写 `DASHSCOPE_API_KEY`、`AUTH_USER`、`AUTH_PASSWORD`。

构建时服务器需要下载两样东西：基础镜像 `python:3.12-slim`（来自 Docker Hub）和 Python 依赖包（来自 PyPI）。默认使用官方源；只有下载很慢或失败时，才需要在 `.env` 里修改：

- `PIP_INDEX_URL`：依赖包的下载源，例如 `https://mirrors.aliyun.com/pypi/simple/`
- `PYTHON_IMAGE`：基础镜像地址，换成公司或云厂商提供的 Docker 镜像站，例如 `<镜像站地址>/library/python:3.12-slim`

改完后启动：

```bash
docker compose up -d --build
```

打开 `http://服务器地址:8765`（端口可通过 `PUBLISH_PORT` 修改）。

常用命令：

```bash
docker compose ps                  # 状态，正常时显示 healthy
docker compose logs -f             # 查看日志
git pull && docker compose up -d --build   # 更新版本
docker compose down                # 停止（数据保留）
```

**数据**：所有项目（大纲和图片）都保存在名为 `ookoo-keynote-forge_keynote-data` 的 Docker 数据卷里。重建或更新容器不会丢失数据；只有 `docker compose down -v` 会删除它。备份：

```bash
docker run --rm -v ookoo-keynote-forge_keynote-data:/data -v "$PWD":/backup alpine tar czf /backup/keynote-data.tgz -C /data .
```

**注意事项**

- **安全**：不填 `AUTH_USER` / `AUTH_PASSWORD` 时，任何能访问这个端口的人都能使用，费用记在你的百炼账号上。Basic 登录的密码是明文传输的，对外网开放时请在前面加 HTTPS 反向代理。
- **反向代理超时**：生成大纲的请求要等 1～2 分钟才返回（换成推理模型时更久）。用 Nginx 时必须调大超时，否则会报 504：
  ```nginx
  location / {
      proxy_pass http://127.0.0.1:8765;
      proxy_read_timeout 600s;
      proxy_send_timeout 600s;
  }
  ```
- **只能单实例运行**：生成任务排在进程内存里，不要开多个副本或多个 worker。重启容器时，正在生成的页面会被标记为失败，需要重新点生成。

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
- 只有一个共用账号，所有登录用户能看到彼此的项目
