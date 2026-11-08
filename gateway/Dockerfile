FROM python:3.11-slim

# Copy the official Astral uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app/gateway

# Optimize python and uv execution
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install dependencies in a separate cached layer
COPY gateway/pyproject.toml gateway/uv.lock ./
COPY orchestrators/naive/pyproject.toml /app/orchestrators/naive/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-project --no-install-package layover-naive

# Copy application code
COPY gateway/ ./
COPY orchestrators/naive/ /app/orchestrators/naive/

# Complete project installation
RUN uv sync --frozen --no-dev

# Use the virtual environment's executables
ENV PATH="/app/gateway/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
