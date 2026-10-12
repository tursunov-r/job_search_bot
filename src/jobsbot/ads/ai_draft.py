"""AI-drafted ad copy — shared by the Telegram "📝 Отправить всем сейчас"
flow (admin_menu.py) and the web admin API (web/routers/ads.py), so the
prompt and the Gemini call live in exactly one place.
"""

from pathlib import Path

from jobsbot.ai.gemini_client import generate

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "docs" / "gemini_promts" / "ad_draft.md"
_PROMPT_TEXT = _PROMPT_PATH.read_text(encoding="utf-8")


async def draft_ad_copy(tezisy: str) -> str:
    """Raises GeminiError on failure — same type callers already catch
    for every other Gemini-backed feature in this project."""
    return await generate(f"{_PROMPT_TEXT}\n{tezisy}")
