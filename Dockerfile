# Multi-stage Dockerfile for smart-pdf-md (PyInstaller onefile)

FROM python:3.11-slim AS build

WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libglib2.0-0 libx11-6 \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --upgrade pip \
  && python -m pip install pyinstaller pymupdf marker-pdf \
  && pyinstaller -F --strip -n smart-pdf-md src/smart_pdf_md/__main__.py

# Align runtime glibc with build image to avoid GLIBC mismatch for PyInstaller
FROM python:3.11-slim AS final
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libx11-6 \
  && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/dist/smart-pdf-md /usr/local/bin/smart-pdf-md
ENTRYPOINT ["/usr/local/bin/smart-pdf-md"]
