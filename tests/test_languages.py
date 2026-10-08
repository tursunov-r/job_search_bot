from jobsbot.processing.languages import CATEGORIES, detect_languages, language_matches, languages_in_category


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


def test_detects_devops():
    assert detect_languages("DevOps Engineer", "") == ["devops"]
    assert detect_languages("Инженер DevOps", "") == ["devops"]


def test_detects_sysadmin():
    assert detect_languages("Системный администратор", "") == ["sysadmin"]


def test_detects_qa():
    assert detect_languages("Тестировщик", "") == ["qa"]
    assert detect_languages("QA Engineer", "") == ["qa"]


def test_mobile_languages_are_in_mobile_category():
    mobile_keys = {lang.key for lang in languages_in_category("mobile")}
    assert mobile_keys == {"kotlin", "swift", "dart"}


def test_javascript_is_in_both_frontend_and_backend():
    assert "javascript" in {lang.key for lang in languages_in_category("frontend")}
    assert "javascript" in {lang.key for lang in languages_in_category("backend")}


def test_devops_sysadmin_qa_categories():
    assert {lang.key for lang in languages_in_category("devops")} == {"devops"}
    assert {lang.key for lang in languages_in_category("sysadmin")} == {"sysadmin"}
    assert {lang.key for lang in languages_in_category("qa")} == {"qa"}


def test_every_language_belongs_to_at_least_one_category():
    from jobsbot.processing.languages import LANGUAGES

    categorized = {lang.key for cat in CATEGORIES for lang in languages_in_category(cat)}
    assert categorized == set(LANGUAGES.keys())


def test_language_matches_genuine_posting():
    assert language_matches("dart", "Senior Flutter Developer", None) is True


def test_language_matches_rejects_unrelated_posting():
    # Confirmed live: HH pads a sparse search term ("flutter") with
    # unrelated postings once genuine matches run out past page 1.
    assert language_matches("dart", "Менеджер по продажам", None) is False


def test_language_matches_unknown_key_is_false():
    assert language_matches("not_a_real_language", "Anything", None) is False
