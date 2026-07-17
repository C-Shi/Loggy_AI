# Setup Guide

Step-by-step instructions to provision, run locally, and deploy Loggy AI on Google Cloud.

## Prerequisites

- Python 3.13+
- Node.js 20+ (Dashboard)
- Docker
- Terraform (>= 1.5 recommended; CI uses 1.15.x)
- Google Cloud SDK (`gcloud`)
- A GCP project with billing enabled
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/) or Google Cloud)

Authenticate for local development:

```sh
gcloud auth login
gcloud auth application-default login
gcloud config set project <Your Project ID>
```

## GCP project prep

1. Enable APIs used by the stack (Logging, Pub/Sub, Eventarc, Cloud Run, Artifact Registry, Firestore, Secret Manager, IAP).
2. Create a GCS bucket for Terraform remote state (used as the backend).
3. Store the Gemini API key in Secret Manager as secret id `gemini-key` (matches Cloud Run `--set-secrets`).
4. For CI/CD: create a CI service account (e.g. `cicd-sa`) and Workload Identity Federation (WIF) so GitHub Actions can authenticate without long-lived keys. Configure repository variables:
   - `GOOGLE_PROJECT`
   - `BUCKET_NAME` (Terraform state bucket)
   - `WORKLOAD_IDENTITY_PROVIDER`

## Infrastructure (Terraform)

From the repo root:

```sh
cd terraform
terraform init -backend-config="bucket=<Your Bucket>"
terraform plan -var="project_id=<Your Project ID>"
terraform apply -var="project_id=<Your Project ID>"
```

This provisions (among other resources):

- Runtime and caller service accounts + least-privilege IAM
- Artifact Registry repos (`loggy-ai-service`, `loggy-ai-dashboard`)
- Secret Manager secret `gemini-key` (+ runtime accessor binding)
- Pub/Sub topic, Logging sink (`severity >= ERROR`), Eventarc trigger
- Dead-letter queue (DLQ) and related subscription settings
- Firestore Native database `loggy-ai-report` and composite indexes
- Identity-Aware Proxy (IAP) scaffolding for the Dashboard

**Note:** Terraform references existing Cloud Run services (`loggy-ai-service`, `loggy-ai-dashboard`) for IAM bindings. On a brand-new project, deploy those services once (manual or CI) before a full apply succeeds, or apply in stages after the first image push.

Region used throughout: `us-west1`.

## Run locally

### Analyzer

```sh
cd service
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a local `.env` in `service/` (do not commit secrets):

```env
GEMINI_API_KEY=<Your Gemini API Key>
PROJECT_ID=<Your Project ID>
```

Start the API:

```sh
fastapi dev api/main.py
```

- Health: `GET http://127.0.0.1:8000/health`
- Request-based analysis: `POST /run` with an LQL/filter config body
- Event-based path: `POST /trigger` with a Pub/Sub / Eventarc-style payload (see `service/tools/mock_event_generator.py`)

ADC must be able to read Cloud Logging (and Firestore if exercising the event/persist path).

Optional tests:

```sh
pip install -r requirements-dev.txt
pytest --cov=service --cov=api --cov-report=term-missing
```

### Dashboard

Requires ADC with access to the Firestore database `loggy-ai-report`:

```sh
cd dashboard
npm install
npm run dev
```

- Web UI: http://localhost:5173 (Vite proxies `/api` → the Express API)
- API: http://localhost:3001

Optional overrides:

```sh
export PROJECT_ID=<Your Project ID>
export FIRESTORE_DATABASE=loggy-ai-report
```

Code defaults (if unset): project example `devops-cert-440119`, database `loggy-ai-report`.

| Command | What it does |
|---------|----------------|
| `npm run dev` | Express API + Vite together |
| `npm run build` | Build React into `dist/` |
| `npm start` | Production-style: API serves `dist/` + `/api` |

## Deploy

### Automated (CI/CD)

On `main`, GitHub Actions:

1. **Service Tests** — pytest in `service/`
2. **Terraform** — plan on PRs; apply on push to `main`
3. **Cloud Run** — after Terraform succeeds, verifies Service Tests for the same SHA, then builds and deploys Analyzer + Dashboard

Analyzer deploy sets `GEMINI_API_KEY` from Secret Manager (`gemini-key:latest`) and `PROJECT_ID`. Dashboard deploy uses `--iap` and `--no-allow-unauthenticated`.

### Manual Cloud Run (optional)

Replace placeholders. Ensure Artifact Registry repos and the runtime SA exist (from Terraform).

**Analyzer**

```sh
gcloud auth configure-docker us-west1-docker.pkg.dev
cd service
docker build --platform="linux/amd64" -t loggy-ai:latest .
docker tag loggy-ai:latest us-west1-docker.pkg.dev/<Your Project ID>/loggy-ai-service/loggy-ai:latest
docker push us-west1-docker.pkg.dev/<Your Project ID>/loggy-ai-service/loggy-ai:latest

gcloud run deploy loggy-ai-service \
  --image=us-west1-docker.pkg.dev/<Your Project ID>/loggy-ai-service/loggy-ai:latest \
  --region=us-west1 \
  --no-allow-unauthenticated \
  --platform=managed \
  --service-account=sa-loggy-ai-runtime@<Your Project ID>.iam.gserviceaccount.com \
  --set-secrets="GEMINI_API_KEY=gemini-key:latest" \
  --set-env-vars="PROJECT_ID=<Your Project ID>"
```

**Dashboard**

```sh
cd dashboard
docker build --platform="linux/amd64" -t loggy-ai-dashboard:latest .
docker tag loggy-ai-dashboard:latest us-west1-docker.pkg.dev/<Your Project ID>/loggy-ai-dashboard/loggy-ai-dashboard:latest
docker push us-west1-docker.pkg.dev/<Your Project ID>/loggy-ai-dashboard/loggy-ai-dashboard:latest

gcloud run deploy loggy-ai-dashboard \
  --image=us-west1-docker.pkg.dev/<Your Project ID>/loggy-ai-dashboard/loggy-ai-dashboard:latest \
  --region=us-west1 \
  --no-allow-unauthenticated \
  --iap \
  --platform=managed \
  --service-account=sa-loggy-ai-runtime@<Your Project ID>.iam.gserviceaccount.com \
  --set-env-vars="PROJECT_ID=<Your Project ID>"
```

Add your user (or group) to the Dashboard IAP allowlist in IAM / IAP console so you can open the UI.

## Verify

**Analyzer (local)**

```sh
curl http://127.0.0.1:8000/health
```

**Analyzer (Cloud Run)** — service is not public; use an identity token:

```sh
curl -X GET "https://loggy-ai-service-<hash>-<region>.a.run.app/health" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

**Dashboard** — open the Cloud Run URL in a browser while signed in as an IAP-allowed identity, or hit `/api/health` through the same auth path.
