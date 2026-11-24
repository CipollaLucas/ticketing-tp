FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY events_service ./events_service
RUN pip install --no-cache-dir -e '.[dev]'
COPY alembic.ini .
COPY alembic ./alembic
COPY tests ./tests
EXPOSE 8002
CMD ["uvicorn", "events_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
