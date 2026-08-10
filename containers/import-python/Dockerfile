FROM python:3.11.9-slim-bookworm@sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317

LABEL org.opencontainers.image.source="https://github.com/GMiguelAlves/HelixForge"
LABEL org.opencontainers.image.description="Python adapter runtime for HelixForge Import API"
LABEL org.opencontainers.image.version="1.0.0"

RUN apt-get update \
    && apt-get install --yes --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*
