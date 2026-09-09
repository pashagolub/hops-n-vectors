#!/usr/bin/env bash
# Build USB-stick tarballs of the workshop image, one per architecture.
set -euo pipefail
IMAGE="${1:-ghcr.io/pashagolub/hops-n-vectors:pg18}"
OUT="${2:-dist}"
mkdir -p "$OUT"
for arch in amd64 arm64; do
    echo "==> pulling ${IMAGE} (${arch})"
    docker pull --platform "linux/${arch}" "$IMAGE"
    target="${OUT}/hops-n-vectors-pg18-${arch}.tar.gz"
    echo "==> saving ${target}"
    docker save "$IMAGE" | gzip -6 > "$target"
    du -h "$target"
done
cp workshop/README.md "${OUT}/README.md"
echo "Copy ${OUT}/ to the USB sticks."
