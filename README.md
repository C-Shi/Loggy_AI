# Loggy AI - Cloud-Native Log Anomaly Detector/Analyzer

A cloud-native, production-ready platform tool designed to ingest distributed cloud logging payloads, programmatically interface with cloud log query semantics, and expose structured operational metrics. This engine serves as the core foundation for automated real-time AIOps evaluation and alerting pipelines.

---

## 🏗️ Architecture & System Design (Phase 1 Baseline)

The current iteration establishes a secure, containerized, and automated end-to-end Infrastructure-as-Code (IaC) deployment pipeline inside Google Cloud Platform (GCP).

### Core Design Decisions & Engineering Trade-offs

1. **Infrastructure as Code (IaC)**: Hand-crafted configurations via the web console are avoided. The entire platform's resource footprint—including Google Cloud Run services, IAM permissions, and artifact registries—is systematically declared and managed via Terraform & CICD.

2. **Least-Privilege Security Boundaries**: The Cloud Run service operates under a dedicated, isolated IAM Service Account. Project-level access policies are strictly bound to permit only log-reading routines (`roles/logging.logViewer`), defending the perimeter against over-provisioning vulnerabilities.

3. **Decoupled Adapter Layer**: The internal parsing engine uses a dedicated Python wrapper module that is platform agnostic, which works with GCP, AWS and Azure. This project choose to implement on Google Cloud, but a dedicate python package is published and can be use independently with other cloud platform. It completely abstracts the cloud query semantics from the presentation layer (FastAPI), outputting clean, universal JSON representations.

### 🛠️ Tech Stack & Ecosystem

- **Backend Engine**: Python 3.13+, FastAPI
- **Cloud Infrastructure**: Google Cloud Run (Serverless Compute), Google Cloud Artifact Registry
- **Observability Interfacing**: Google Cloud Logging API
- **Deployment Orchestration**: Terraform, Github Action, Docker

### 🚀 Implemented Capabilities

#### 1.Programmatic Log Ingestion Adapter

- Developed an extensible core Python module that targets Google Cloud Logging endpoints dynamically.
- Dynamically parses custom syntax expressions, returning standardized structured JSON arrays optimized for secondary pipeline consumers.

#### 2.High-Performance API Gateway

- Implemented an asynchronous FastAPI service layer acting as the cloud platform ingress.
- Configured payload schema endpoints to dynamically accept custom filter configurations and forward structured logging streams seamlessly.

#### 3.Container Optimization & Secure Deployment

- Configured a minimal, multi-stage Dockerfile optimizing image footprint and caching layers for swift serverless cold-start execution.
- Implemented automatic compilation and pushes to Google Cloud Artifact Registry alongside automated, version-tracked serverless rollouts to Google Cloud Run.

### Local Setup

1. **Clone the repository**

2. **Initialize Infrastructure**

   To provision or sync state structures locally using GCS as the unified remote state storage backend

   ```sh
   cd infra
   terraform init -backend-config="bucket=<Your Bucket>"
   terraform apply -var="project_id=<Your Project ID>"

   ```

3. **Run Application Locally**

   ```sh
   python -m venv venv
   source venv/bin/activate
   cd services/loggy_ai
   pip install -r requirements.txt
   fastapi dev main.py
   ```

4. **Manual Deployment To Cloud Run**

   ```
   gcloud auth configure-docker us-west1-docker.pkg.dev
   cd services/loggy_ai
   docker build --platform="linux/amd64" -t loggy-ai:latest .
   docker tag loggy-ai:latest us-west1-docker.pkg.dev/devops-cert-440119/loggy-ai-image/loggy-ai:latest
   docker push us-west1-docker.pkg.dev/devops-cert-440119/loggy-ai-image/loggy-ai:latest

   gcloud run deploy loggy-ai-service \
   --image=us-west1-docker.pkg.dev/devops-cert-440119/loggy-ai-image/loggy-ai:latest \
   --region=us-west1 \
   --allow-unauthenticated \
   --platform=managed \
   --service-account=sa-loggy-ai-runtime@devops-cert-440119.iam.gserviceaccount.com
   ```

#### Test

```

curl -X GET "https://loggy-ai-service-944405268355.us-west1.run.app/health" \
-H "Authorization: bearer $(gcloud auth print-identity-token)"

```

```

```
