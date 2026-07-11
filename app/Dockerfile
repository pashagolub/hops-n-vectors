# Multi-stage: take the pg_timetable binary from the official image
# (static Go binary, multi-arch) — spec v1.2 CON-006.
# hadolint ignore=DL3007
FROM cybertecpostgresql/pg_timetable:latest AS timetable

FROM python:3.12-slim

WORKDIR /app

# Install CPU-only PyTorch first.  The dedicated whl index hosts CPU builds for
# both x86_64 and arm64 Linux; doing this before the rest of the package avoids
# pulling the larger default (CUDA) wheel that PyPI serves on x86_64.
RUN pip install --no-cache-dir \
        "torch>=2.0" \
        --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY --from=timetable /pg_timetable /usr/local/bin/pg_timetable

COPY hopsnvectors/ hopsnvectors/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default: load -> embed -> exec pg_timetable (PAT-001).
# Pass "tui" (or "loader"/"embedder") as the first arg to run a tool instead.
ENTRYPOINT ["/entrypoint.sh"]

