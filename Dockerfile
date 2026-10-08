FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

COPY alembic.ini .
COPY alembic/ alembic/
COPY reset_vacancies.py .
COPY seed_group_topics.py .
COPY backfill_group_topic_baseline.py .

CMD ["python", "-m", "jobsbot.main"]
