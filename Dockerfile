FROM python:3.13-slim AS base

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Default: JSONL backend, self mode
ENV HIVEMIND_MODE=self
ENV HIVEMIND_BACKEND=jsonl
ENV HIVEMIND_JSONL_PATH=/data/memory.jsonl

VOLUME /data

ENTRYPOINT ["hivemind-mcp"]

# ── With MongoDB support ──
FROM base AS mongodb
RUN pip install --no-cache-dir ".[mongodb]"
ENV HIVEMIND_BACKEND=mongodb
ENTRYPOINT ["hivemind-mcp"]

# ── With PostgreSQL support ──
FROM base AS postgres
RUN pip install --no-cache-dir ".[postgres]"
ENV HIVEMIND_BACKEND=postgres
ENTRYPOINT ["hivemind-mcp"]

# ── With Redis support ──
FROM base AS redis
RUN pip install --no-cache-dir ".[redis]"
ENV HIVEMIND_BACKEND=redis
ENTRYPOINT ["hivemind-mcp"]

# ── With all backends ──
FROM base AS all
RUN pip install --no-cache-dir ".[all]"
ENTRYPOINT ["hivemind-mcp"]
