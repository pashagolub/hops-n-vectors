# syntax=docker/dockerfile:1.7
#
# Hops'n'Vectors workshop image — everything an attendee needs in one pull:
#   PostgreSQL 18 + pgvector + pg_cron + plpython3u + ONNX Runtime
#   + a quantized all-MiniLM-L12-v2 model + 12,656 pre-embedded beers.
#
#   docker run -d --name beer -p 5432:5432 ghcr.io/pashagolub/hops-n-vectors:pg18
#   docker exec -it beer psql
#
# Build from the repository root:
#   docker build -f workshop/Dockerfile -t hops-n-vectors-workshop .
FROM postgres:18-bookworm

# sentence-transformers/all-MiniLM-L12-v2, ONNX export.
# Default is the int8 quantization (34 MB); pass MODEL_FILE=model.onnx with its
# checksum for the fp32 original (133 MB).
ARG HF_REPO=sentence-transformers/all-MiniLM-L12-v2
ARG HF_REV=a50ef00143b4d5391434df20ae11632588ac25be
ARG MODEL_FILE=onnx/model_qint8_avx512.onnx
ARG MODEL_SHA256=d37479e69ddcb2f7af2ae225a41cb57b0b6fd547dd8740aef4f0c8e5b41d4fcf
ARG TOKENIZER_PATH=tokenizer.json
ARG QUERY_PREFIX=
ARG DOCUMENT_PREFIX=
ARG TOKENIZER_SHA256=be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037
ARG ONNXRUNTIME_VERSION=1.29.0
ARG TOKENIZERS_VERSION=0.23.2

# PostgreSQL extensions: pgvector for the vector type and HNSW,
# plpython3u to run the model, pg_cron to keep embeddings fresh.
# The PGDG apt repository is already configured in the official image.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        postgresql-$PG_MAJOR-pgvector \
        postgresql-plpython3-$PG_MAJOR \
        postgresql-$PG_MAJOR-cron \
        python3-pip; \
    pip install --no-cache-dir --break-system-packages --target /opt/pyembed \
        "onnxruntime==${ONNXRUNTIME_VERSION}"; \
    # tokenizers only needs huggingface_hub for from_pretrained(); this image
    # loads tokenizer.json from disk, so the whole HTTP client stack is skipped.
    pip install --no-cache-dir --break-system-packages --target /opt/pyembed \
        --no-deps "tokenizers==${TOKENIZERS_VERSION}"; \
    find /opt/pyembed -name '__pycache__' -type d -prune -exec rm -rf {} +; \
    rm -rf /opt/pyembed/bin; \
    apt-get purge -y --auto-remove python3-pip; \
    rm -rf /var/lib/apt/lists/*

# plpython3u runs inside the backend, so the model libraries must be importable
# by the server's embedded interpreter.
ENV PYTHONPATH=/opt/pyembed \
    HNV_MODEL_DIR=/opt/model \
    HNV_MAX_SEQ_LENGTH=128 \
    HNV_ORT_THREADS=2 \
    HNV_QUERY_PREFIX=${QUERY_PREFIX} \
    HNV_DOCUMENT_PREFIX=${DOCUMENT_PREFIX} \
    HNV_MODEL_NAME=${HF_REPO}

ADD --checksum=sha256:${MODEL_SHA256} \
    https://huggingface.co/${HF_REPO}/resolve/${HF_REV}/${MODEL_FILE} \
    /opt/model/model.onnx
ADD --checksum=sha256:${TOKENIZER_SHA256} \
    https://huggingface.co/${HF_REPO}/resolve/${HF_REV}/${TOKENIZER_PATH} \
    /opt/model/tokenizer.json
RUN chmod 0444 /opt/model/model.onnx /opt/model/tokenizer.json

# Demo credentials, baked so `docker run` needs no -e flags and
# `docker exec -it beer psql` needs no arguments.
ENV POSTGRES_USER=beer \
    POSTGRES_PASSWORD=beer \
    POSTGRES_DB=beer \
    PGUSER=beer \
    PGDATABASE=beer \
    PSQLRC=/workshop/psqlrc

# Executed in filename order on first start by the official entrypoint.
COPY init/01_schema.sql       /docker-entrypoint-initdb.d/01_schema.sql
COPY workshop/sql/10_embed.sql /docker-entrypoint-initdb.d/
COPY workshop/db/             /docker-entrypoint-initdb.d/
COPY workshop/sql/30_index.sql workshop/sql/40_helpers.sql \
     workshop/sql/50_cron.sql workshop/sql/90_ready.sql \
     /docker-entrypoint-initdb.d/

COPY workshop/exercises/ /workshop/
COPY workshop/psqlrc workshop/verify.sql /workshop/

# pg_cron must be preloaded, and the entrypoint passes these to the
# temporary init server too, so 50_cron.sql can create the extension.
CMD ["postgres", \
     "-c", "shared_preload_libraries=pg_cron", \
     "-c", "cron.database_name=beer", \
     "-c", "cron.use_background_workers=on"]

# The init server listens on the unix socket only, so a TCP probe stays
# unhealthy until the database is genuinely ready for attendees.
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=60 \
    CMD pg_isready -h 127.0.0.1 -U beer -d beer
