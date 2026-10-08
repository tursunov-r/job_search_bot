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


def test_detects_kotlin():
    assert detect_languages("Kotlin Developer", "") == ["kotlin"]


def test_detects_swift_in_title_but_not_banking_swift_in_description():
    assert detect_languages("Swift Developer", "") == ["swift"]
    # A single keyword can never reach the description tier's >=2
    # threshold, so a banking/fintech post mentioning SWIFT transfers
    # only in the description (never in the title) won't false-positive.
    assert detect_languages("Backend Developer", "Интеграция с SWIFT-платежами") == []


def test_detects_dart_via_flutter_or_dart():
    assert detect_languages("Flutter Developer", "") == ["dart"]
    assert detect_languages("Dart Developer", "") == ["dart"]
