FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY identity ./identity
RUN pip install --no-cache-dir -e '.[dev]'
COPY alembic.ini .
COPY alembic ./alembic
COPY tests ./tests
EXPOSE 8001
CMD ["uvicorn", "identity.main:app", "--host", "0.0.0.0", "--port", "8001"]
