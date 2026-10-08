from jobsbot.processing.work_formats import categorize


def test_none_text_has_no_categories():
    assert categorize(None) == set()


def test_remote_text():
    assert categorize("удалённо") == {"remote"}
    assert categorize("Можно удалённо") == {"remote"}


def test_office_text():
    assert categorize("на месте работодателя") == {"office"}


def test_hybrid_text():
    assert categorize("гибрид") == {"hybrid"}


def test_multiple_categories_in_one_string():
    assert categorize("на месте работодателя, удалённо или гибрид") == {"office", "remote", "hybrid"}


def test_case_insensitive():
    assert categorize("УДАЛЁННО") == {"remote"}
