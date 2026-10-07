from jobsbot.ingestion.habr_adapter import _parse_page, _parse_vacancy_details

CARD_WITH_REAL_SALARY = """
<div class="vacancy-card">
  <div class="vacancy-card__company"><a>Acme</a></div>
  <div class="vacancy-card__title"><a class="vacancy-card__title-link" href="/vacancies/111">Python Developer</a></div>
  <div class="vacancy-card__salary"><div class="basic-salary">от 230 000 ₽</div></div>
  <div class="vacancy-card__meta"><div class="vacancy-meta">
    <div class="basic-chip"><svg class="svg-icon svg-icon--icon-grade"></svg><div class="chip-with-icon__text">Middle</div></div>
    <div class="basic-chip"><svg class="svg-icon svg-icon--icon-placemark"></svg><div class="chip-with-icon__text">Москва</div></div>
  </div></div>
</div>
"""

CARD_WITH_PREDICTED_SALARY = """
<div class="vacancy-card">
  <div class="vacancy-card__company"><a>Beta</a></div>
  <div class="vacancy-card__title"><a class="vacancy-card__title-link" href="/vacancies/222">Go Developer</a></div>
  <div class="vacancy-card__salary"><div class="predicted-salary">
    <h4>Зарплата не указана</h4><span>Похожие специалисты получают 150 000 - 250 000 ₽</span>
  </div></div>
  <div class="vacancy-card__meta"><div class="vacancy-meta">
    <div class="basic-chip"><svg class="svg-icon svg-icon--icon-grade"></svg><div class="chip-with-icon__text">Senior</div></div>
    <div class="basic-chip"><svg class="svg-icon svg-icon--icon-format"></svg><div class="chip-with-icon__text">Можно удалённо</div></div>
  </div></div>
</div>
"""

DETAIL_HTML = """
<html><body>
<div class="vacancy-description__text"><p>Нужен опытный разработчик для нашей команды.</p></div>
</body></html>
"""


def test_parse_page_uses_real_salary_not_predicted():
    vacancies = _parse_page(CARD_WITH_REAL_SALARY)
    assert len(vacancies) == 1
    assert vacancies[0].salary_text == "от 230 000 ₽"
    assert vacancies[0].experience == "Middle"
    assert vacancies[0].location == "Москва"
    assert vacancies[0].work_format is None


def test_parse_page_ignores_predicted_salary():
    vacancies = _parse_page(CARD_WITH_PREDICTED_SALARY)
    assert len(vacancies) == 1
    assert vacancies[0].salary_text is None
    assert vacancies[0].experience == "Senior"
    assert vacancies[0].location is None
    assert vacancies[0].work_format == "Можно удалённо"


def test_parse_page_builds_canonical_url():
    vacancies = _parse_page(CARD_WITH_REAL_SALARY)
    assert vacancies[0].url == "https://career.habr.com/vacancies/111"


def test_parse_vacancy_details_extracts_description():
    details = _parse_vacancy_details(DETAIL_HTML)
    assert details.description == "Нужен опытный разработчик для нашей команды."


def test_parse_vacancy_details_missing_description_is_none():
    details = _parse_vacancy_details("<html><body>ничего нет</body></html>")
    assert details.description is None
