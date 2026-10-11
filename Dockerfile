# 国内服务器拉取慢时，可在 .env 中把 PYTHON_IMAGE / PIP_INDEX_URL 换成镜像源
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    UV_INDEX_URL=${PIP_INDEX_URL} \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install uv

# 先只装依赖，代码改动时可以复用这一层缓存。
# uv sync 会直接用 uv.lock 里记录的 pypi.org 下载地址、无视镜像源，
# 所以先导出带哈希的依赖清单，再按 PIP_INDEX_URL 安装：版本和文件仍与 uv.lock 完全一致。
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python --require-hashes -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY app.py ./
COPY core ./core
COPY static ./static

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/projects \
    && chown -R app:app /data
USER app

ENV HOST=0.0.0.0 \
    PORT=8765 \
    PROJECTS_DIR=/data/projects

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz', timeout=4)"

CMD ["python", "app.py"]
