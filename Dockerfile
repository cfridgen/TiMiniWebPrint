# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS pybuilder

WORKDIR /build

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential liblzo2-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM debian:bookworm-slim AS nodeexporter

ARG NODE_EXPORTER_VERSION=1.8.2
ARG TARGETARCH

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl tar \
  && rm -rf /var/lib/apt/lists/*

RUN build_arch="${TARGETARCH:-}" \
  && if [ -z "${build_arch}" ]; then build_arch="$(dpkg --print-architecture)"; fi \
  && case "${build_arch}" in \
    amd64|x86_64) exporter_arch="amd64" ;; \
    arm64|aarch64) exporter_arch="arm64" ;; \
    *) echo "Unsupported architecture: ${build_arch}" >&2; exit 1 ;; \
  esac \
  && curl -fsSL "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-${exporter_arch}.tar.gz" \
    | tar -xz -C /tmp \
  && mv "/tmp/node_exporter-${NODE_EXPORTER_VERSION}.linux-${exporter_arch}/node_exporter" /node_exporter

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ADDR=0.0.0.0 \
    APP_PORT=8000 \
    NODE_EXPORTER_ADDR=:9100

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends liblzo2-2 tini bluez dbus \
  && rm -rf /var/lib/apt/lists/*

COPY --from=pybuilder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
  && rm -rf /wheels

COPY --from=nodeexporter /node_exporter /usr/local/bin/node_exporter
COPY docker/entrypoint.sh /entrypoint.sh

COPY timiniprint /app/timiniprint
COPY timiniprint_web.py /app/timiniprint_web.py

RUN chmod +x /entrypoint.sh /usr/local/bin/node_exporter

EXPOSE 8000 9100

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/entrypoint.sh"]
