#### Deploy To Cloud Run

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
