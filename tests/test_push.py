from jobsbot.bot.push import _matches_city, _matches_work_format
from jobsbot.storage.models import Vacancy


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
