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

COPY hopsnvectors/ hopsnvectors/

# Compose services override CMD to select loader / embedder / tui.
ENTRYPOINT ["python", "-m"]
CMD ["hopsnvectors.loader"]

