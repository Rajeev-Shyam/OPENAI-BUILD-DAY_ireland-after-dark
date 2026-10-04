FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY backend ./backend
COPY data/__init__.py ./data/__init__.py
COPY data/pipeline ./data/pipeline
COPY data/*sources.json ./data/
RUN mkdir -p data/raw data/processed

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
