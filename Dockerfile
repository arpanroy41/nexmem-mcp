FROM python:3.13-slim AS base

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir .

# Default: JSONL backend, self mode
ENV NEXMEM_MODE=self
ENV NEXMEM_BACKEND=jsonl
ENV NEXMEM_JSONL_PATH=/data/memory.jsonl

VOLUME /data

ENTRYPOINT ["nexmem-mcp"]

# ── With MongoDB support ──
FROM base AS mongodb
RUN pip install --no-cache-dir ".[mongodb]"
ENV NEXMEM_BACKEND=mongodb
ENTRYPOINT ["nexmem-mcp"]

# ── With PostgreSQL support ──
FROM base AS postgres
RUN pip install --no-cache-dir ".[postgres]"
ENV NEXMEM_BACKEND=postgres
ENTRYPOINT ["nexmem-mcp"]

# ── With Redis support ──
FROM base AS redis
RUN pip install --no-cache-dir ".[redis]"
ENV NEXMEM_BACKEND=redis
ENTRYPOINT ["nexmem-mcp"]

# ── With all backends ──
FROM base AS all
RUN pip install --no-cache-dir ".[all]"
ENTRYPOINT ["nexmem-mcp"]
