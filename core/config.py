import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com").rstrip("/")
TEXT_MODEL = os.getenv("TEXT_MODEL", "qwen3.8-max")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "qwen-image-3.0")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "2048*1152")
CONCURRENCY = int(os.getenv("CONCURRENCY", "3"))
MOCK_MODE = os.getenv("MOCK_MODE", "0") == "1"

PROJECTS_DIR = ROOT / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)
