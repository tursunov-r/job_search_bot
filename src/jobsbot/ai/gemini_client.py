"""Minimal Gemini REST client — plain httpx, no SDK, consistent with the
rest of the project (same spirit as the ingestion adapters).

Uses the public generateContent REST endpoint directly rather than
google-genai/google-generativeai, since the only thing needed here is
"send a prompt + an optional inline file, get text back" — pulling in a
whole SDK for that would be overkill.
"""

import asyncio
import base64
import logging

import httpx

from jobsbot.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
REQUEST_TIMEOUT_SECONDS = 120.0

# Confirmed live: gemini-3.8-flash returns 503 "high demand, try again
# later" fairly often even under normal load — a bare retry (no backoff
# needed, it's not a hard rate limit) succeeded immediately every time
# this was observed, so retrying a couple of times beats surfacing a
# transient failure as "try again later" to the user on the first miss.
RETRYABLE_STATUS_CODES = {503, 429}
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 3.0


class GeminiError(Exception):
    """Raised for any Gemini failure — missing key, HTTP error, empty/
    blocked response, or an unexpected response shape. Callers only need
    to catch this one type and show the user a generic retry message."""


async def generate(prompt: str, file_bytes: bytes | None = None, mime_type: str | None = None) -> str:
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY не задан")

    parts: list[dict] = [{"text": prompt}]
    if file_bytes is not None and mime_type is not None:
        parts.append(
            {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(file_bytes).decode("ascii")}}
        )

    url = f"{API_BASE}/{settings.gemini_model}:generateContent"
    payload = {"contents": [{"parts": parts}]}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await client.post(url, params={"key": settings.gemini_api_key}, json=payload)
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                logger.warning("Gemini request failed: %s — %s", exc, exc.response.text[:500])
                if exc.response.status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_ATTEMPTS:
                    raise GeminiError(f"Gemini вернул ошибку: {exc.response.status_code}") from exc
            except httpx.HTTPError as exc:
                logger.warning("Gemini request failed: %s", exc)
                raise GeminiError("Не удалось связаться с Gemini") from exc

            logger.info("Retrying Gemini request (attempt %d/%d)", attempt + 1, MAX_ATTEMPTS)
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback")
        logger.warning("Gemini returned no candidates: %s", feedback)
        raise GeminiError(f"Gemini не вернул ответ (возможно, заблокировано: {feedback})")

    parts_out = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts_out).strip()
    if not text:
        finish_reason = candidates[0].get("finishReason")
        raise GeminiError(f"Gemini вернул пустой ответ (finishReason={finish_reason})")

    return text
