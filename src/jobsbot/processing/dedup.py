import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_COMPANY_SUFFIXES_RE = re.compile(
    r"\b(ооо|оао|зао|ип|llc|inc|ltd|gmbh)\b", re.IGNORECASE
)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = _HTML_TAG_RE.sub(" ", text)
    text = text.lower()
    text = _COMPANY_SUFFIXES_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def fingerprint(title: str, company: str | None, description: str | None) -> str:
    parts = [
        normalize_text(title),
        normalize_text(company),
        normalize_text((description or "")[:500]),
    ]
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
