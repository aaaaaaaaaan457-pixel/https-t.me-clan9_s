import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:  # mahalliy sinov uchun .env
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def get(name, default=None, required=True):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"{name} topilmadi (.env yoki GitHub Secrets'ga qo'ying)")
    return value


RUBRIC = "Claude maslahatlar"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_v3")
MAX_TRIES = 3  # sifat nazoratidan o'tmasa, necha marta qayta yozish
