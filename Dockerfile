FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

COPY alembic.ini .
COPY alembic/ alembic/

CMD ["python", "-m", "jobsbot.main"]
