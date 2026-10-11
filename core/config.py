import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com").rstrip("/")
TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen-plus")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "qwen-image-3.0")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "2048*1152")
CONCURRENCY = int(os.getenv("CONCURRENCY", "3"))
MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"

# 本机开发只监听 127.0.0.1；容器里设为 0.0.0.0
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))

# 两项都填写时启用 HTTP Basic 登录
AUTH_USER = os.getenv("AUTH_USER", "")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")

PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", ROOT / "projects"))
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
