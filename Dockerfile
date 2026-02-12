FROM python:3.9-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/

WORKDIR /app

# Install dependencies using uv
COPY pyproject.toml .
RUN /uv/bin/uv pip install --system .

COPY exporter.py .

CMD ["python", "exporter.py"]
