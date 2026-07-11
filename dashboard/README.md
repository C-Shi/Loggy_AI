# Loggy AI Dashboard

React + Node dashboard over Firestore `reports`. Same layout that will later run as one Cloud Run service (static UI + thin API).

## Local development

Requires Application Default Credentials with access to the `loggy-ai-report` Firestore database:

```sh
gcloud auth application-default login
# optional overrides:
# export PROJECT_ID=devops-cert-440119
# export FIRESTORE_DATABASE=loggy-ai-report

cd dashboard
npm install
npm run dev
```

- Web UI: http://localhost:5173 (Vite proxies `/api` → API)
- API: http://localhost:3001

## Scripts

| Command | What it does |
|---------|----------------|
| `npm run dev` | API + Vite together |
| `npm run build` | Build React into `dist/` |
| `npm start` | Production-style: API serves `dist/` + `/api` |

## Data

- Project: `PROJECT_ID` / `GOOGLE_CLOUD_PROJECT` (default `devops-cert-440119`)
- Database: `FIRESTORE_DATABASE` (default `loggy-ai-report`)
- Collection: `reports`
- Chart: sums `incident_count` grouped by `business_impact`
