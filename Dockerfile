FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TEXTDOC_ROOT=/app TEXTDOC_STUDIO_DATA=/app/studio-data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml requirements-studio.txt ./
COPY textdoc ./textdoc
COPY textdoc_studio ./textdoc_studio
COPY run_studio.py run-studio.sh ./
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e . -r requirements-studio.txt
RUN mkdir -p /app/studio-data/projects /app/voices && chmod +x /app/run-studio.sh
EXPOSE 8014
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -fsS http://127.0.0.1:8014/ >/dev/null || exit 1
CMD ["python", "run_studio.py"]
