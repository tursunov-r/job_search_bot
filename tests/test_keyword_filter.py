from jobsbot.processing.keyword_filter import is_python_vacancy


def test_title_match():
    assert is_python_vacancy("Python-разработчик", "")


def test_title_match_english():
    assert is_python_vacancy("Senior Python Developer", "")


def test_no_match():
    assert not is_python_vacancy("Менеджер по продажам", "Опыт работы с клиентами")


def test_description_requires_two_matches():
    assert not is_python_vacancy("Backend Developer", "Будет плюсом знание python")
    assert is_python_vacancy("Backend Developer", "Используем python, django и celery")


def test_deny_list_without_python_in_title():
    assert not is_python_vacancy("QA Engineer", "Немного python для автоматизации")


def test_deny_list_overridden_by_python_in_title():
    assert is_python_vacancy("Python QA Engineer", "")
