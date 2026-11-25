FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY ticketing_service ./ticketing_service
RUN pip install --no-cache-dir -e '.[dev]'
COPY alembic.ini .
COPY alembic ./alembic
COPY tests ./tests
COPY h4_confirmed_order_smoke.py ./h4_confirmed_order_smoke.py
COPY h4_concurrent_http_smoke.py ./h4_concurrent_http_smoke.py
COPY h5_gateway_smoke.py ./h5_gateway_smoke.py
EXPOSE 8003
CMD ["uvicorn", "ticketing_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
