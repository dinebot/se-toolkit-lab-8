# syntax=docker/dockerfile:1

# Stage 1: Build the Python environment
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

WORKDIR /app/nanobot

# Copy dependency files and workspace dependencies
COPY pyproject.toml .python-version ./
COPY --from=workspace /uv.lock ./uv.lock
COPY --from=workspace /mcp ./mcp
COPY --from=workspace /nanobot-websocket-channel ./nanobot-websocket-channel

# Install dependencies
RUN uv sync --frozen --no-dev

# Install webchat plugin from local path
RUN uv add ./nanobot-websocket-channel/nanobot-webchat --editable

# Stage 2: Runtime image
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app/nanobot

# Copy the virtual environment from builder
COPY --from=builder /app/nanobot/.venv /app/nanobot/.venv

# Copy application files
COPY . .

# Copy nanobot-websocket-channel for editable install
COPY --from=workspace /nanobot-websocket-channel ./nanobot-websocket-channel

# Copy mcp for MCP server
COPY --from=workspace /mcp ./mcp

# Make entrypoint executable
RUN chmod +x entrypoint.py

# Set PATH to include uv
ENV PATH="/app/nanobot/.venv/bin:$PATH"

CMD ["python", "/app/nanobot/entrypoint.py"]
