from jobsbot.processing.dedup import fingerprint, normalize_text


def test_normalize_strips_html_and_punctuation():
    assert normalize_text("<b>Python</b>-разработчик!") == "python разработчик"


def test_normalize_strips_company_suffix():
    assert normalize_text('ООО "Ромашка"') == "ромашка"


def test_fingerprint_stable_for_identical_input():
    fp1 = fingerprint("Python Developer", "Acme", "Great job")
    fp2 = fingerprint("Python Developer", "Acme", "Great job")
    assert fp1 == fp2


def test_fingerprint_differs_for_different_title():
    fp1 = fingerprint("Python Developer", "Acme", "Great job")
    fp2 = fingerprint("Java Developer", "Acme", "Great job")
    assert fp1 != fp2


def test_fingerprint_insensitive_to_whitespace_and_case():
    fp1 = fingerprint("Python Developer", "Acme", "desc")
    fp2 = fingerprint("  python   developer  ", "ACME", "DESC")
    assert fp1 == fp2
