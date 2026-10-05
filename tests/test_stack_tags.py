from jobsbot.processing.stack_tags import matches_stack


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
