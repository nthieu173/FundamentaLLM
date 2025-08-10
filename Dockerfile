FROM ghcr.io/astral-sh/uv:alpine

WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies into a local virtual environment
RUN uv sync --frozen --no-progress

# Copy application source
COPY backend ./backend

# Prepare runtime environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

