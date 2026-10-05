from jobsbot.ingestion.linkedin_adapter import _parse_page

SAMPLE_HTML = """
<ul>
  <li>
    <div class="base-card relative w-full base-search-card base-search-card--link job-search-card"
         data-entity-urn="urn:li:jobPosting:123">
      <a class="base-card__full-link" href="https://ru.linkedin.com/jobs/view/python-dev-at-acme-123?trk=x">
        <span class="sr-only">Python Developer</span>
      </a>
      <div class="base-search-card__info">
        <h3 class="base-search-card__title">Python Developer</h3>
        <h4 class="base-search-card__subtitle">
          <a href="#">Acme</a>
        </h4>
        <div class="base-search-card__metadata">
          <span class="job-search-card__location">Moscow, Russia</span>
        </div>
      </div>
    </div>
  </li>
</ul>
"""


def test_parse_page_extracts_vacancy():
    vacancies = _parse_page(SAMPLE_HTML)
    assert len(vacancies) == 1
    v = vacancies[0]
    assert v.title == "Python Developer"
    assert v.company == "Acme"
    assert v.location == "Moscow, Russia"
    assert v.url == "https://ru.linkedin.com/jobs/view/python-dev-at-acme-123"


def test_parse_page_empty_html():
    assert _parse_page("<html></html>") == []
