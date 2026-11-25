FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY events_service ./events_service
RUN pip install --no-cache-dir -e '.[dev]'
COPY alembic.ini .
COPY alembic ./alembic
COPY tests ./tests
COPY h3_contract_smoke.py ./h3_contract_smoke.py
COPY h4_live_smoke.py ./h4_live_smoke.py
COPY h4_fault_proxy.py ./h4_fault_proxy.py
COPY h4_fault_recovery_smoke.py ./h4_fault_recovery_smoke.py
EXPOSE 8002
CMD ["uvicorn", "events_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
