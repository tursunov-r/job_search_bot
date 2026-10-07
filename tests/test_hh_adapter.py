from jobsbot.ingestion.hh_adapter import _parse_page, _parse_vacancy_details

LISTING_HTML_WITH_SALARY = """
<article data-qa="vacancy-serp__vacancy">
  <a data-qa="serp-item__title" href="https://hh.ru/vacancy/123?query=python">
    <span data-qa="serp-item__title-text">Python Developer</span>
  </a>
  <span data-qa="vacancy-serp__vacancy-employer-text">Acme</span>
  <span data-qa="vacancy-serp__vacancy-address">Москва</span>
  <div><span><data value="100000">100 000</data> – <data value="150000">150 000 </data><data value="RUB">₽</data> за месяц, на руки</span></div>
</article>
"""

LISTING_HTML_NO_SALARY = """
<article data-qa="vacancy-serp__vacancy">
  <a data-qa="serp-item__title" href="https://hh.ru/vacancy/456">
    <span data-qa="serp-item__title-text">Go Developer</span>
  </a>
</article>
"""

DETAIL_HTML = """
<html><body>
<p>Опыт работы: <span data-qa="vacancy-experience">3–6 лет</span></p>
<div data-qa="common-employment-text"><span>Полная занятость</span></div>
<p data-qa="work-schedule-by-days-text">График: 5/2</p>
<div data-qa="working-hours-text"><span>Рабочие часы: 8</span></div>
<p data-qa="work-formats-text">Формат работы: удалённо</p>
<div data-qa="vacancy-description"><p>Нужен опытный разработчик.</p></div>
</body></html>
"""


def test_parse_page_extracts_salary_from_data_tags():
    vacancies = _parse_page(LISTING_HTML_WITH_SALARY)
    assert len(vacancies) == 1
    assert vacancies[0].salary_text == "100 000 – 150 000 ₽ за месяц, на руки"


def test_parse_page_without_salary_leaves_it_none():
    vacancies = _parse_page(LISTING_HTML_NO_SALARY)
    assert len(vacancies) == 1
    assert vacancies[0].salary_text is None


def test_parse_vacancy_details_extracts_all_fields():
    details = _parse_vacancy_details(DETAIL_HTML)
    assert details.experience == "3–6 лет"
    assert details.employment_type == "Полная занятость"
    assert details.schedule == "5/2, 8 часов"
    assert details.work_format == "удалённо"
    assert details.description == "Нужен опытный разработчик."


def test_parse_vacancy_details_missing_fields_are_none():
    details = _parse_vacancy_details("<html><body>ничего нет</body></html>")
    assert details.experience is None
    assert details.employment_type is None
    assert details.schedule is None
    assert details.work_format is None
    assert details.description is None
