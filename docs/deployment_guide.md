# Cloud Deployment Guide

This project is two independently deployable services sharing one image
(`Dockerfile`):

- **API** — the FastAPI backend (`deployment/app.py`), the agent itself.
- **UI** — the Streamlit app (`deployment/streamlit_app.py`), a thin HTTP
  client of the API (`API_BASE_URL`).

Deploy the API first, then point the UI at its URL. Three ways to do this,
simplest to most control:

## Option A — Google Cloud Run (recommended: simplest, serverless, scales to zero)

```bash
# 1. Deploy the API
gcloud run deploy bharat-motors-support-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars USE_MOCK_LLM=true
# note the printed Service URL, e.g. https://bharat-motors-support-api-xyz.a.run.app

# 2. Deploy the UI, pointed at the API
gcloud run deploy bharat-motors-support-ui \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --command streamlit \
  --args="run,deployment/streamlit_app.py,--server.port=8080,--server.address=0.0.0.0,--server.headless=true" \
  --set-env-vars API_BASE_URL=https://bharat-motors-support-api-xyz.a.run.app
```
`--source .` builds the `Dockerfile` for you (once per service — same
image, different `--command`/`--args`). Cloud Run injects `$PORT`
automatically; both `deployment/config.py` (API) and the `--server.port`
flag above (UI) are wired to use it. To use the real LLM backend instead
of the offline default on the API service, add
`--set-env-vars USE_MOCK_LLM=false --set-secrets GOOGLE_API_KEY=google-api-key:latest`
(after creating the secret with `gcloud secrets create`).

**Caveat:** Cloud Run instances are stateless/ephemeral by default — see
"Known limitation: session state" below before relying on multi-turn memory
or the RLHF feedback loop in production.

## Option B — Google App Engine Flexible for the API (uses `app.yaml` + `Dockerfile`)

```bash
gcloud app deploy app.yaml
```
`app.yaml` deploys the **API only** (App Engine Flexible runs the
Dockerfile's default `CMD`, which is `uvicorn deployment.app:app`) — it
configures autoscaling, health checks (`/health`), and non-secret env
vars. Set `GOOGLE_API_KEY` via Secret Manager rather than editing
`app.yaml`. Deploy the Streamlit UI as a separate Cloud Run service (see
the comment block at the bottom of `app.yaml`, or Option A above) pointed
at the App Engine service's URL.

## Option C — Any Docker host (a VM, DigitalOcean/EC2/Azure VM, bare metal)

```bash
cp .env.example .env        # edit if using the real LLM backend
docker compose up --build -d
```
`docker-compose.yml` runs **both services** from one image — API on
`:8080`, UI on `:8501`, wired together automatically (`API_BASE_URL=http://api:8080`
inside the compose network) — and mounts `./logs` and `./data` as volumes
so interaction logs and RLHF feedback state persist across container
restarts, which the managed-platform options (A/B) don't do by default
(see below).

Plain `docker run` also works without compose, one container per service:
```bash
docker build -t bharat-motors-support-agent .

docker run -d -p 8080:8080 --env-file .env --name api bharat-motors-support-agent

docker run -d -p 8501:8501 -e API_BASE_URL=http://<api-host>:8080 --name ui \
  bharat-motors-support-agent \
  streamlit run deployment/streamlit_app.py --server.port=8501 --server.address=0.0.0.0
```

## Verifying a deployment

```bash
# API
curl https://<api-url>/health
curl -X POST https://<api-url>/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"smoketest","message":"Is my car under warranty?"}'
# FastAPI auto-generates interactive docs too:
open https://<api-url>/docs

# UI
open https://<ui-url>          # chat in the browser
```

## Known limitation: session state

`agent/memory.py`'s `MemoryStore` and `policy_rlhf/feedback_collector.py`'s
feedback store are **in-process / local-disk** by design (see
`docs/engineering_justification.md` §7). This matters for cloud deployment
specifically:

- **Cloud Run / App Engine with >1 API instance:** a customer's follow-up
  message can land on a different instance with no memory of the earlier
  turn, and `data/rlhf/feedback_store.json` writes won't be shared across
  instances (App Engine Flexible's `session_affinity: true` in `app.yaml`
  mitigates this *within a single deploy*, but instances can still be
  recycled). For real production multi-turn memory, swap `MemoryStore`'s
  in-process dict for Redis/Firestore — the class's public interface
  (`get`, `reset`) is small enough to reimplement as a thin wrapper without
  touching `agent/core_agent.py`.
- **The Streamlit UI itself is stateless across browser sessions** by
  design — `st.session_state` lives only in that browser tab's session; a
  page refresh starts a new `session_id`. This is intentional (matches how
  a real customer support widget behaves) and independent of the API-side
  limitation above.
- **Docker Compose / single VM (Option C):** the API-side limitation
  doesn't apply — one API process, one disk, state persists naturally via
  the mounted volumes.

## Environment variables reference

See `.env.example` for the full list. The two that matter most in the
cloud:
- `USE_MOCK_LLM` (API): `true` (default) runs fully offline with no
  external calls; `false` requires `GOOGLE_API_KEY` and outbound network
  access to Google's Generative Language API.
- `API_BASE_URL` (UI only): the deployed API's URL. Defaults to
  `http://localhost:8080` for local development.
