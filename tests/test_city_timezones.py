from jobsbot.processing.city_timezones import resolve_city_timezone


def test_known_city_resolves():
    assert resolve_city_timezone(["Москва"]) == "Europe/Moscow"
    assert resolve_city_timezone(["Алматы"]) == "Asia/Almaty"


def test_case_insensitive():
    assert resolve_city_timezone(["МОСКВА"]) == "Europe/Moscow"
    assert resolve_city_timezone(["москва"]) == "Europe/Moscow"


def test_unrecognized_city_returns_none():
    assert resolve_city_timezone(["Атлантида"]) is None


def test_empty_list_returns_none():
    assert resolve_city_timezone([]) is None


def test_first_recognized_city_wins():
    assert resolve_city_timezone(["Атлантида", "Новосибирск", "Москва"]) == "Asia/Novosibirsk"


def test_different_zones_for_different_cities():
    # Confirms the whole point of this module — RU/CIS spans many zones.
    assert resolve_city_timezone(["Владивосток"]) != resolve_city_timezone(["Москва"])
