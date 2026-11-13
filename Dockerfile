# StaleBot — dashboard + API image.
#   docker build -t stalebot .
#   docker run --env-file .env -e APP_ENV=production -p 8000:8000 -v stalebot-data:/data stalebot
# Build with --build-arg WITH_STREAMLIT=true to also include the optional Streamlit UI (app.py).
FROM python:3.14-slim

ARG WITH_STREAMLIT=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt requirements-streamlit.txt ./
RUN if [ "$WITH_STREAMLIT" = "true" ]; then pip install -r requirements-streamlit.txt; \
    else pip install -r requirements.txt; fi

COPY detector.py security.py server.py app.py ./
COPY static ./static
COPY .streamlit ./.streamlit

# Run as an unprivileged user; history is written to the /data volume.
RUN useradd --create-home --uid 10001 stalebot \
    && mkdir -p /data && chown stalebot:stalebot /data
USER stalebot
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/healthz', timeout=4)"

# Single process on purpose: the JSON store and rate limiter live in memory of this process.
CMD ["python", "server.py"]
