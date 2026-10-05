from jobsbot.ingestion.telegram_listener import build_message_url, parse_message_text


def test_parse_message_basic():
    raw = parse_message_text("🐍 Python Developer (Remote)\nЗП: 250-300k\nКомпания: Acme")
    assert raw is not None
    assert raw.title == "Python Developer (Remote)"
    assert "ЗП: 250-300k" in raw.description


def test_parse_message_strips_leading_emoji_only_from_title():
    raw = parse_message_text("🔥🔥 Срочно нужен Django разработчик")
    assert raw is not None
    assert raw.title == "Срочно нужен Django разработчик"


def test_parse_message_empty_text():
    assert parse_message_text("") is None
    assert parse_message_text(None) is None
    assert parse_message_text("   \n   ") is None


def test_build_message_url():
    assert build_message_url("python_jobs", 42) == "https://t.me/python_jobs/42"
    assert build_message_url(None, 42) is None
