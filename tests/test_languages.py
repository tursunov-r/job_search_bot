from jobsbot.processing.languages import detect_languages


def test_detects_python_in_title():
    assert detect_languages("Python Developer", "") == ["python"]


def test_no_match_returns_empty_list():
    assert detect_languages("Менеджер по продажам", "Опыт работы с клиентами") == []


def test_description_requires_two_matches():
    assert detect_languages("Backend Developer", "Будет плюсом знание python") == []
    assert detect_languages("Backend Developer", "Пишем на python, местами питон-скрипты") == ["python"]


def test_detects_javascript_without_colliding_with_java():
    assert detect_languages("JavaScript Developer", "") == ["javascript"]
    assert detect_languages("TypeScript Developer", "") == ["javascript"]
