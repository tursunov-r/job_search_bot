from jobsbot.processing.stack_tags import UNIVERSAL_TAG_KEYS, matches_stack, visible_tag_keys


def test_no_selection_matches_everything():
    assert matches_stack("Python Developer", "Какой-то текст без технологий", [])


def test_matches_one_of_selected_tags():
    assert matches_stack("Python Developer", "Используем Redis и PostgreSQL", ["redis"])


def test_matches_any_selected_tag_not_all():
    assert matches_stack("Python Developer", "Используем Kafka", ["redis", "kafka"])


def test_no_match_when_keyword_absent():
    assert not matches_stack("Python Developer", "Используем MongoDB", ["redis", "kafka"])


def test_match_in_title_without_description():
    assert matches_stack("Python/Django Developer", None, ["django"])


def test_unknown_tag_key_is_ignored_safely():
    assert not matches_stack("Python Developer", "обычный текст", ["not_a_real_tag"])


def test_visible_tags_with_no_language_is_just_universal():
    assert visible_tag_keys([]) == UNIVERSAL_TAG_KEYS


def test_visible_tags_includes_python_tags_when_python_selected():
    tags = visible_tag_keys(["python"])
    assert "django" in tags
    assert "fastapi" in tags
    for universal in UNIVERSAL_TAG_KEYS:
        assert universal in tags


def test_visible_tags_includes_mobile_tags():
    assert "jetpackcompose" in visible_tag_keys(["kotlin"])
    assert "swiftui" in visible_tag_keys(["swift"])
    assert "getx" in visible_tag_keys(["dart"])


def test_matches_mobile_stack_tag_in_title():
    assert matches_stack("Flutter Developer (BLoC)", None, ["bloc"])
