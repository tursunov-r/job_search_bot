from jobsbot.ingestion.remoteok_adapter import _format_salary, _parse_entry, _strip_html

LEGAL_NOTICE = {"legal": "API Terms of Service: ..."}

REAL_JOB_ENTRY = {
    "slug": "remote-senior-python-dev-acme-1137475",
    "id": "1137475",
    "date": "2026-10-09T13:09:18+00:00",
    "company": "Acme",
    "position": "Senior Python Developer",
    "tags": ["dev", "python", "remote"],
    "description": "<p>We need a <strong>Python</strong> developer.</p><ul><li>Django</li></ul>",
    "location": "",
    "salary_min": 80000,
    "salary_max": 200000,
    "url": "https://remoteOK.com/remote-jobs/remote-senior-python-dev-acme-1137475",
    "apply_url": "https://remoteOK.com/remote-jobs/remote-senior-python-dev-acme-1137475",
}


def test_strip_html_removes_tags_and_collapses_whitespace():
    assert _strip_html("<p>We need a <strong>Python</strong>  developer.</p>") == "We need a Python developer."


def test_strip_html_none_is_none():
    assert _strip_html(None) is None


def test_format_salary_range():
    assert _format_salary(80000, 200000) == "$80,000–$200,000 / год"


def test_format_salary_single_value_when_equal():
    assert _format_salary(100000, 100000) == "$100,000 / год"


def test_format_salary_only_one_side_present():
    assert _format_salary(None, 150000) == "$150,000 / год"


def test_format_salary_both_missing_is_none():
    assert _format_salary(None, None) is None


def test_parse_entry_skips_legal_notice():
    assert _parse_entry(LEGAL_NOTICE) is None


def test_parse_entry_extracts_real_job():
    raw = _parse_entry(REAL_JOB_ENTRY)
    assert raw is not None
    assert raw.title == "Senior Python Developer"
    assert raw.company == "Acme"
    assert raw.description == "We need a Python developer. Django"
    assert raw.url == REAL_JOB_ENTRY["url"]
    assert raw.salary_text == "$80,000–$200,000 / год"
    assert raw.work_format == "удалённо"
    assert raw.posted_at is not None
    assert raw.posted_at.year == 2026 and raw.posted_at.month == 10 and raw.posted_at.day == 9


def test_parse_entry_handles_missing_date_gracefully():
    entry = {**REAL_JOB_ENTRY, "date": None}
    raw = _parse_entry(entry)
    assert raw.posted_at is None


def test_parse_entry_falls_back_to_apply_url_when_url_missing():
    entry = {**REAL_JOB_ENTRY}
    del entry["url"]
    raw = _parse_entry(entry)
    assert raw.url == REAL_JOB_ENTRY["apply_url"]
