import httpx
import pytest
import respx

from jobsbot.ai import gemini_client
from jobsbot.config import settings


@pytest.fixture(autouse=True)
def _gemini_configured(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-2.0-flash")


@pytest.mark.asyncio
@respx.mock
async def test_generate_text_only_returns_text():
    respx.post(f"{gemini_client.API_BASE}/gemini-2.0-flash:generateContent").mock(
        return_value=httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Привет!"}]}, "finishReason": "STOP"}]},
        )
    )
    result = await gemini_client.generate("скажи привет")
    assert result == "Привет!"


@pytest.mark.asyncio
@respx.mock
async def test_generate_sends_inline_file_when_given():
    route = respx.post(f"{gemini_client.API_BASE}/gemini-2.0-flash:generateContent").mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        )
    )
    await gemini_client.generate("анализируй файл", file_bytes=b"%PDF-1.4 fake", mime_type="application/pdf")

    request_body = route.calls.last.request.content
    import json

    payload = json.loads(request_body)
    parts = payload["contents"][0]["parts"]
    assert parts[0]["text"] == "анализируй файл"
    assert parts[1]["inline_data"]["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_generate_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    with pytest.raises(gemini_client.GeminiError):
        await gemini_client.generate("привет")


@pytest.mark.asyncio
@respx.mock
async def test_generate_raises_on_empty_candidates():
    respx.post(f"{gemini_client.API_BASE}/gemini-2.0-flash:generateContent").mock(
        return_value=httpx.Response(200, json={"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})
    )
    with pytest.raises(gemini_client.GeminiError, match="SAFETY"):
        await gemini_client.generate("скажи что-то запрещённое")


@pytest.mark.asyncio
@respx.mock
async def test_generate_raises_on_http_error():
    respx.post(f"{gemini_client.API_BASE}/gemini-2.0-flash:generateContent").mock(
        return_value=httpx.Response(500, text="internal error")
    )
    with pytest.raises(gemini_client.GeminiError):
        await gemini_client.generate("привет")
