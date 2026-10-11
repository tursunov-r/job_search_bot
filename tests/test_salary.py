from jobsbot.processing.salary import parse_salary_min_rub


def test_range_in_rub_takes_lower_bound():
    assert parse_salary_min_rub("от 100 000 до 130 000 ₽") == 100000


def test_fixed_amount_in_rub():
    assert parse_salary_min_rub("60 000 ₽ за месяц на руки") == 60000


def test_upper_bound_only_is_unknown():
    assert parse_salary_min_rub("до 100 000 ₽") is None


def test_non_rub_currency_is_unknown():
    assert parse_salary_min_rub("от 500 до 3 500 $ за месяц на руки") is None
    assert parse_salary_min_rub("от 2 500 до 3 000 Br за месяц до вычета налогов") is None
    assert parse_salary_min_rub("от 5 000 000 до 10 000 000 so'm за месяц на руки") is None


def test_no_salary_text_is_none():
    assert parse_salary_min_rub(None) is None
    assert parse_salary_min_rub("") is None


def test_nbsp_thousand_separator_is_handled():
    assert parse_salary_min_rub("от\xa0100\xa0000\xa0₽ за месяц на руки") == 100000
