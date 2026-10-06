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


def test_detects_go_via_golang_not_bare_go():
    assert detect_languages("Golang Developer", "") == ["go"]
    assert detect_languages("Let's go get coffee", "") == []


def test_detects_java_without_matching_inside_javascript():
    assert detect_languages("Java Developer", "") == ["java"]
    assert detect_languages("JavaScript Developer", "") == ["javascript"]


def test_detects_csharp_via_hash_and_dotnet_variants():
    assert detect_languages("C# Developer", "") == ["csharp"]
    assert detect_languages(".NET Developer", "") == ["csharp"]
    assert detect_languages("ASP.NET Backend Developer", "") == ["csharp"]


def test_detects_php():
    assert detect_languages("PHP Developer", "") == ["php"]


def test_detects_ruby():
    assert detect_languages("Ruby on Rails Developer", "") == ["ruby"]
