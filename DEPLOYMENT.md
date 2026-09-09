# Render Deployment

## No-Payment Option

Use **GitHub Pages for the frontend** and a **free Hugging Face Docker Space for
the FastAPI backend**. This avoids Render billing, but the backend may sleep
when idle and the free storage/compute limits may require using the smaller
sample dataset instead of the full cached snapshot.

1. Create a Hugging Face Space with Docker and copy the backend service files,
   `model/`, `data/`, `requirements.txt`, and `mplads_sentinel.db` into it.
2. Start the Space with:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

3. Set `CORS_ORIGINS` in the Space to your GitHub Pages URL.
4. Build the frontend with the Space API URL:

```bash
cd frontend
npm ci
$env:VITE_API_BASE_URL="https://YOUR-SPACE.hf.space"
npm run build
```

5. Publish the generated `frontend/dist/` folder using GitHub Pages.

GitHub Pages cannot run the FastAPI backend by itself. The backend and frontend
must therefore be hosted separately. For a lighter free demo, set
`MPLADS_DATASET_PATH=data/mplads_raw_sample.csv` and use the 776-work sample;
the full SQLite database and cached CSV may exceed free Space storage limits.

This project deploys as two Render services:

- `mplads-sentinel-api`: FastAPI backend on Render's `$PORT`
- `mplads-sentinel-frontend`: static Vite build

## Deploy

1. Push this project to a GitHub or GitLab repository. Keep the selected SQLite snapshot and `data/last_live_feed.csv` available to the build.
2. In Render, choose **New > Blueprint** and select the repository.
3. Render detects `render.yaml` and creates both services.
4. Copy the backend service URL, for example `https://mplads-sentinel-api.onrender.com`.
5. Set `VITE_API_BASE_URL` on the frontend service to that backend URL, then trigger a new deploy.
6. Open the frontend service URL and verify `/api/health` through the dashboard.

The blueprint configures demo CORS as `*` because this prototype uses the
`X-User-Role` header rather than cookie credentials. Restrict `CORS_ORIGINS` to
the exact frontend URL before production use.

The backend health endpoint is:

```text
https://YOUR-BACKEND.onrender.com/api/health
```

## Important SQLite Note

The current deployment uses the bundled SQLite snapshot for a prototype demo. Render web-service filesystems are ephemeral on free services, so review logs and any database changes can be lost after a restart or redeploy. Use a persistent Render disk or PostgreSQL before treating this as a production system.

The active local snapshot is selected with:

```env
MPLADS_DATASET_PATH=data/last_live_feed.csv
```

To use the smaller bundled sample instead:

```env
MPLADS_DATASET_PATH=data/mplads_raw_sample.csv
```

Do not run the 6-minute snapshot rebuild during every deploy. The checked-in SQLite database is already scored; use `py -m backend.seeder --force --source live-cache` locally when deliberately rebuilding it.

## Local Production Build

```bash
cd frontend
npm ci
npm run build
```

Backend:

```bash
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```
