#### Run Fast API Image Locally

```
    docker run -d \
    --name loggy-ai \
    -p 8000:8000 \
    -v "$HOME/.config/gcloud:/tmp/gcloud:ro" \
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcloud/application_default_credentials.json \
    -e PORT=8000 \
    loggy-ai
```
