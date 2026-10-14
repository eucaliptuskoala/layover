FROM python:3.11-slim

# Copy the official Astral uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Optimize python and uv execution
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install dependencies in a separate cached layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Complete project installation
RUN uv sync --frozen --no-dev

# Ensure persistent database directory exists
RUN mkdir -p /app/data

# Use the virtual environment's executables
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
