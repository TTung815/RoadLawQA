# Two images from one file:
#   api - FastAPI + retrieval (torch CPU, embedding/reranker), no model weights inside
#   ui  - Streamlit client only (HTTP to the API), no ML dependencies
# Built and run by docker/docker-compose.yml; see docs/SETUP.md.

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 1000 app
WORKDIR /app


FROM base AS ui
COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install -r frontend/requirements.txt
COPY frontend/ frontend/
USER app
EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]


FROM base AS api
# CPU-only torch first: the default x86 wheel bundles CUDA (several GB) that
# a container on a laptop cannot use. requirements.txt then finds it installed.
RUN pip install torch==2.5.1 --extra-index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Writable for the app user: saved chats (a volume) and the HF cache root, where
# the embedding model's remote code is unpacked next to the read-only hub mount.
RUN mkdir -p outputs/chat /home/app/.cache/huggingface \
    && chown -R app:app outputs /home/app/.cache
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
