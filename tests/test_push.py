from datetime import datetime
from unittest.mock import patch

import jobsbot.bot.push as push_module
from jobsbot.bot.push import (
    _is_quiet_now,
    _matches_city,
    _matches_keywords,
    _matches_salary,
    _matches_work_format,
    _matching_candidate_count,
    _vacancy_matches,
)
from jobsbot.storage.models import Subscriber, Vacancy


def _vacancy(**overrides) -> Vacancy:
    defaults = dict(
        fingerprint="fp",
        title="Python Developer",
        source_id=1,
        raw_source_ids="[]",
        languages="[]",
    )
    defaults.update(overrides)
    return Vacancy(**defaults)


def _subscriber(**overrides) -> Subscriber:
    defaults = dict(
        telegram_user_id=1,
        languages="[]",
        skills="[]",
        cities="[]",
        work_formats="[]",
        keywords="[]",
    )
    defaults.update(overrides)
    return Subscriber(**defaults)


def test_no_city_filter_matches_everything():
    vacancy = _vacancy(location="Москва", work_format="на месте работодателя")
    assert _matches_city(vacancy, None) is True
    assert _matches_city(vacancy, []) is True


def test_matching_city_passes():
    vacancy = _vacancy(location="Москва", work_format="на месте работодателя")
    assert _matches_city(vacancy, ["Москва"]) is True
    assert _matches_city(vacancy, ["москва"]) is True  # case-insensitive


def test_matching_any_of_multiple_cities_passes():
    vacancy = _vacancy(location="Казань", work_format="на месте работодателя")
    assert _matches_city(vacancy, ["Москва", "Казань"]) is True


def test_mismatched_city_fails():
    vacancy = _vacancy(location="Санкт-Петербург", work_format="на месте работодателя")
    assert _matches_city(vacancy, ["Москва"]) is False


def test_no_location_fails_without_remote_hint():
    vacancy = _vacancy(location=None, work_format="гибрид")
    assert _matches_city(vacancy, ["Москва"]) is False


def test_remote_bypasses_city_filter_even_with_different_location():
    # HH-style: employer's city set, but the role itself is remote.
    vacancy = _vacancy(location="Новосибирск", work_format="удалённо")
    assert _matches_city(vacancy, ["Москва"]) is True


def test_remote_bypasses_city_filter_with_no_location():
    # Habr-style: no location at all for "Можно удалённо".
    vacancy = _vacancy(location=None, work_format="Можно удалённо")
    assert _matches_city(vacancy, ["Москва"]) is True


def test_hybrid_without_remote_hint_still_requires_city_match():
    vacancy = _vacancy(location="Казань", work_format="гибрид")
    assert _matches_city(vacancy, ["Москва"]) is False
    assert _matches_city(vacancy, ["Казань"]) is True


def test_no_work_format_filter_matches_everything():
    vacancy = _vacancy(work_format="на месте работодателя")
    assert _matches_work_format(vacancy, []) is True


def test_no_salary_filter_matches_everything():
    vacancy = _vacancy(salary_min_rub=50000)
    assert _matches_salary(vacancy, None) is True


def test_salary_above_threshold_passes():
    vacancy = _vacancy(salary_min_rub=200000)
    assert _matches_salary(vacancy, 150000) is True


def test_salary_below_threshold_fails():
    vacancy = _vacancy(salary_min_rub=50000)
    assert _matches_salary(vacancy, 150000) is False


def test_unknown_salary_passes_filter():
    # Non-RUB currency, "до Y" with no stated floor, or no salary at all —
    # unknown shouldn't be treated as "below threshold".
    vacancy = _vacancy(salary_min_rub=None)
    assert _matches_salary(vacancy, 150000) is True


def test_no_keywords_never_matches_on_its_own():
    vacancy = _vacancy(title="FastAPI service")
    assert _matches_keywords(vacancy, []) is False


def test_keyword_matches_title_case_insensitively():
    vacancy = _vacancy(title="Разработчик FastAPI", description=None)
    assert _matches_keywords(vacancy, ["fastapi"]) is True


def test_keyword_matches_description():
    vacancy = _vacancy(title="Backend Developer", description="Работаем с Apache Airflow")
    assert _matches_keywords(vacancy, ["airflow"]) is True


def test_keyword_no_match():
    vacancy = _vacancy(title="Backend Developer", description="Django, Celery")
    assert _matches_keywords(vacancy, ["fastapi"]) is False


def test_keyword_widens_relevance_past_language_stack_mismatch():
    # Tagged "go", subscriber only wants "python" — without the keyword this
    # would never match; with it, it widens through.
    vacancy = _vacancy(title="Go Developer", description="Интеграция с FastAPI сервисом", languages='["go"]')
    assert _vacancy_matches(vacancy, ["python"], [], None, None, None, None) is False
    assert _vacancy_matches(vacancy, ["python"], [], None, None, None, ["fastapi"]) is True


def test_keyword_widening_still_respects_other_filters():
    vacancy = _vacancy(
        title="Go Developer", description="FastAPI integration", languages='["go"]', location="Новосибирск"
    )
    assert _vacancy_matches(vacancy, ["python"], [], ["Москва"], None, None, ["fastapi"]) is False


def test_matching_candidate_count_for_weekly_digest():
    subscriber = _subscriber(languages='["python"]')
    candidates = [
        _vacancy(fingerprint="d1", languages='["python"]'),
        _vacancy(fingerprint="d2", languages='["go"]'),  # doesn't match -> not counted
        _vacancy(fingerprint="d3", languages='["python"]'),
    ]
    assert _matching_candidate_count(subscriber, candidates) == 2


def test_matching_candidate_count_zero_when_nothing_matches():
    subscriber = _subscriber(languages='["java"]')
    candidates = [_vacancy(fingerprint="d4", languages='["python"]')]
    assert _matching_candidate_count(subscriber, candidates) == 0


def test_work_format_matches_selected_category():
    vacancy = _vacancy(work_format="удалённо")
    assert _matches_work_format(vacancy, ["remote"]) is True
    assert _matches_work_format(vacancy, ["office"]) is False


def test_work_format_matches_any_of_several_selected():
    vacancy = _vacancy(work_format="гибрид")
    assert _matches_work_format(vacancy, ["remote", "hybrid"]) is True


def test_work_format_vacancy_with_multiple_categories():
    # Employer offering either office or remote — should satisfy either preference.
    vacancy = _vacancy(work_format="на месте работодателя, удалённо или гибрид")
    assert _matches_work_format(vacancy, ["office"]) is True
    assert _matches_work_format(vacancy, ["remote"]) is True
    assert _matches_work_format(vacancy, ["hybrid"]) is True


def test_work_format_unknown_fails_when_filter_set():
    vacancy = _vacancy(work_format=None)
    assert _matches_work_format(vacancy, ["remote"]) is False


def _at_hour(hour: int):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 1, hour, tzinfo=tz)

    return patch.object(push_module, "datetime", FixedDatetime)


def test_no_quiet_hours_configured_never_quiet():
    subscriber = _subscriber(quiet_hours_start=None, quiet_hours_end=None)
    assert _is_quiet_now(subscriber) is False


def test_quiet_hours_wrap_past_midnight():
    subscriber = _subscriber(quiet_hours_start=23, quiet_hours_end=8)
    with _at_hour(2):
        assert _is_quiet_now(subscriber) is True
    with _at_hour(12):
        assert _is_quiet_now(subscriber) is False
    with _at_hour(23):
        assert _is_quiet_now(subscriber) is True  # start boundary, inclusive
    with _at_hour(8):
        assert _is_quiet_now(subscriber) is False  # end boundary, exclusive


def test_quiet_hours_same_day_range():
    subscriber = _subscriber(quiet_hours_start=1, quiet_hours_end=6)
    with _at_hour(3):
        assert _is_quiet_now(subscriber) is True
    with _at_hour(10):
        assert _is_quiet_now(subscriber) is False
