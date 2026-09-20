# Bharat Motors Customer Support Agent -- container image
#
# Single image, two possible processes (chosen by CMD/--command at deploy
# time): the FastAPI backend (default) or the Streamlit UI. This mirrors
# how docker-compose.yml runs them as two services from one image, and lets
# a platform like Cloud Run deploy each independently from the same build
# (see docs/deployment_guide.md).
#
# Build:            docker build -t bharat-motors-support-agent .
# Run (API):         docker run -p 8080:8080 --env-file .env bharat-motors-support-agent
# Run (Streamlit):   docker run -p 8501:8501 -e API_BASE_URL=http://<api-host>:8080 \
#                       bharat-motors-support-agent \
#                       streamlit run deployment/streamlit_app.py --server.port=8501 --server.address=0.0.0.0
# (omit --env-file to run fully offline with the default USE_MOCK_LLM=true
#  -- see README "Offline mode")

FROM python:3.11-slim

# build-essential is needed for scikit-learn/numpy source builds on some
# platforms; harmless if wheels are used instead.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project.
COPY . .

# Build the knowledge base at image-build time so the container starts
# ready to serve (Phase 4 ingestion + FAISS index). This re-runs
# deterministically even though knowledge/faiss_index/ already ships
# pre-built in the repo, so the image is correct even if knowledge/raw/*.pdf
# is edited before building.
RUN USE_MOCK_LLM=true python scripts/ingest_documents.py \
    && USE_MOCK_LLM=true python scripts/build_faiss_index.py

# Defaults; override at `docker run -e` / docker-compose.yml / your
# platform's environment-variable settings. USE_MOCK_LLM=true means the
# container runs fully offline out of the box -- set to "false" +
# GOOGLE_API_KEY to use the real LangChain/Google Gemini backend (see
# docs/engineering_justification.md §3). API_BASE_URL is only read by the
# Streamlit process, to reach the FastAPI backend.
ENV USE_MOCK_LLM=true \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    API_BASE_URL=http://localhost:8080

EXPOSE 8080 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8080)}/health', timeout=3)" || exit 1

# Default process: the FastAPI backend, via uvicorn. Shell form so
# ${PORT:-8080} expands at container start (Cloud Run/App Engine inject
# $PORT); `exec` keeps uvicorn as PID 1 for clean signal handling. Override
# this CMD (see the Streamlit run example above, or docker-compose.yml) to
# run the Streamlit UI process from the same image instead.
CMD exec uvicorn deployment.app:app --host 0.0.0.0 --port ${PORT:-8080}
