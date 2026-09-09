# Free demo deployment

This version is designed to avoid the 400–500 MB MPLADS database.

## Data used by the online demo

The backend seeds `data/mplads_raw_sample.csv` on startup. The large SQLite
database and `last_live_feed.csv` are intentionally excluded from this package.

## Backend

The backend is a normal FastAPI application:

    uvicorn backend.main:app --host 0.0.0.0 --port $PORT

Set:

    MPLADS_DATASET_PATH=data/mplads_raw_sample.csv
    CORS_ORIGINS=*

The backend needs a Python host that supports FastAPI. Do not use the old
Render Blueprint configuration in this package.

## Frontend

The frontend is Vite and is prepared for GitHub Pages at:

    https://poulamisingha1212-source.github.io/jan/

The workflow is `.github/workflows/deploy-pages.yml`.

In GitHub repository Settings → Pages, choose GitHub Actions.

Before the frontend deployment, add this repository variable:

    VITE_API_BASE_URL=https://YOUR-BACKEND-URL

The Vite build reads this value.

## Local test

Backend:

    python -m pip install -r requirements.txt
    uvicorn backend.main:app --reload --port 8001

Frontend, in another terminal:

    cd frontend
    npm ci
    npm run dev

The local Vite proxy still sends `/api`, `/works`, `/stats`, and `/sync`
requests to `http://localhost:8001`.

## Important

This is a prototype/demo deployment. It intentionally uses the small sample
dataset rather than the full 400–500 MB database.
