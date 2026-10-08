from jobsbot.ingestion.geekjob_adapter import _parse_page, _parse_vacancy_details

LISTING_HTML = """
<ul class="serp-list">
  <li class="collection-item avatar ">
    <div class="info"><a href="/vacancy/aaa111" target="_blank">
        <br><span class="salary">500K — 750K ₽</span></a></div>
    <p class="truncate vacancy-name"><a href="/vacancy/aaa111" class="title">Senior Full Stack JavaScript разработчик</a></p>
    <p class="truncate company-name"><a href="/vacancy/aaa111"> United Developers </a></p>
    <div class="info"><span class="remote-label">remote</span>&nbsp;</div>
  </li>
  <li class="collection-item avatar ">
    <div class="info"><a href="/vacancy/bbb222" target="_blank">Москва, Россия
        <br><span class="salary"></span></a></div>
    <p class="truncate vacancy-name"><a href="/vacancy/bbb222" class="title">Account Manager</a></p>
    <p class="truncate company-name"><a href="/vacancy/bbb222"> Lofty</a></p>
    <div class="info"><span class="inhouse-label">office</span>&nbsp;</div>
  </li>
  <li class="collection-item avatar ">
    <div class="info"><a href="/vacancy/ccc333" target="_blank">
        <br><span class="salary"></span></a></div>
    <p class="truncate vacancy-name"><a href="/vacancy/ccc333" class="title">Hybrid Python Developer</a></p>
    <p class="truncate company-name"><a href="/vacancy/ccc333"> Acme</a></p>
    <div class="info"><span class="remote-label">remote</span>&nbsp;<span class="inhouse-label">office</span>&nbsp;</div>
  </li>
</ul>
"""

DETAIL_HTML_REMOTE = """
<html><body>
<div class="description"><b>Описание вакансии</b><hr>
<div id="vacancy-description"><p>Мы ищем разработчика в команду.</p></div></div>
<span class="jobformat">Удаленная работа<br>
Опыт работы более 5 лет</span>
</body></html>
"""

DETAIL_HTML_OFFICE = """
<html><body>
<div id="vacancy-description"><p>Работа в офисе, полный день.</p></div>
<span class="jobformat">Работа в офисе<br>
Опыт работы от 1 года до 3х лет</span>
</body></html>
"""


def test_parse_page_extracts_remote_card():
    vacancies = _parse_page(LISTING_HTML)
    assert len(vacancies) == 3
    v = vacancies[0]
    assert v.title == "Senior Full Stack JavaScript разработчик"
    assert v.company == "United Developers"
    assert v.salary_text == "500K — 750K ₽"
    assert v.location is None
    assert v.work_format == "удалённо"
    assert v.url == "https://geekjob.ru/vacancy/aaa111"


def test_parse_page_extracts_office_card_with_location():
    v = _parse_page(LISTING_HTML)[1]
    assert v.title == "Account Manager"
    assert v.salary_text is None
    assert v.location == "Москва, Россия"
    assert v.work_format == "на месте работодателя"


def test_parse_page_both_labels_means_hybrid_ish():
    v = _parse_page(LISTING_HTML)[2]
    assert v.work_format == "на месте работодателя или удалённо"


def test_parse_vacancy_details_remote():
    details = _parse_vacancy_details(DETAIL_HTML_REMOTE)
    assert details.description == "Мы ищем разработчика в команду."
    assert details.work_format == "Удаленная работа"
    assert details.experience == "Опыт работы более 5 лет"


def test_parse_vacancy_details_office():
    details = _parse_vacancy_details(DETAIL_HTML_OFFICE)
    assert details.work_format == "Работа в офисе"
    assert details.experience == "Опыт работы от 1 года до 3х лет"


def test_parse_vacancy_details_missing_everything_is_none():
    details = _parse_vacancy_details("<html><body>ничего нет</body></html>")
    assert details.description is None
    assert details.work_format is None
    assert details.experience is None
