# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install dependencies into a clean venv
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools (for lxml etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into /app/.venv
COPY requirements.txt .
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --upgrade pip && \
    .venv/bin/pip install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Keeps Python from buffering stdout/stderr (so logs appear immediately)
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV PYTHONPATH=/app

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY tempmail/ ./tempmail/
COPY examples/ ./examples/

# Make sure the venv Python is used
ENV PATH="/app/.venv/bin:$PATH"

# Default command: run the interactive Telegram bot
CMD ["python", "examples/interactive_telegram_bot.py"]
