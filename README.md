# MPLADS AI Sentinel — Audit & Anomaly Prioritization Platform
**MoSPI (SIH26102)** — Ministry of Statistics and Programme Implementation

---

## 1. What MPLADS AI Sentinel Does

**MPLADS AI Sentinel** is an AI-assisted audit prioritization and decision-support web platform designed for **MoSPI**. It systematically surfaces potential irregularities, cost outliers, duplicate claims, stagnant implementation, and procurement concentration across works executed under the **Members of Parliament Local Area Development Scheme (MPLADS)**.

> **Crucial Explainability Principle:**  
> The system produces **Risk Tiers (`High Risk - Review`, `Medium Risk - Monitor`, `Low Risk`)** and **Action Directives**, not definitive criminal verdicts. An AI flag is a decision-support filter for audit inspection; only authorized human reviewers can confirm an irregularity or fraud.

---

## 2. Project Architecture

```
project-root/
├── docs/
│   ├── SRS.md                      # Full Software Requirements Specification
│   └── fraud_detection_logic.md    # Evidence-grounded typology & signal mapping
│
├── model/
│   ├── risk_engine.py              # Authoritative risk engine implementation
│   └── agents/                     # Financial, timeline, duplicate, vendor, compliance agents
│
├── data/
│   └── mplads_raw_sample.csv       # MPLADS website export used by the prototype
│
├── backend/
│   ├── config.py                   # Pydantic environment configuration
│   ├── database.py                 # SQLAlchemy session and engine
│   ├── models.py                   # ORM models (Work, ReviewLog, SyncLog)
│   ├── schemas.py                  # Pydantic REST API schemas
│   ├── auth.py                     # Role-Based Access Control (RBAC, fail-closed)
│   ├── seeder.py                   # Chunked idempotent database seeder
│   ├── main.py                     # FastAPI REST API application
│   └── services/
│       ├── ingestion.py            # Static sample loading, scoring & sync logging
│       └── analytics.py            # MP/state directories, chart analytics, CSV export
│
├── frontend/                       # React + Tailwind CSS Dashboard
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui primitives (button, card, dialog, select,
│   │   │   │                       #   table, tabs, badge, input, progress, skeleton,
│   │   │   │                       #   tooltip, dropdown-menu, sonner, textarea)
│   │   │   ├── magicui/            # Magic UI motion components (number-ticker,
│   │   │   │                       #   shimmer-button, animated-shiny-text, dot-pattern,
│   │   │   │                       #   border-beam, blur-fade)
│   │   │   ├── Header.jsx          # MoSPI branding, status pill, role selector
│   │   │   ├── PriorityQueue.jsx   # Default view ordered by priority rank
│   │   │   ├── CasePacketModal.jsx # Detailed dossier with review feedback
│   │   │   ├── PortfolioOverview.jsx # Macro metrics, charts & entity risk ranking
│   │   │   ├── MPDirectory.jsx     # Public MP fund directory (sortable table)
│   │   │   ├── MPProfileModal.jsx  # Per-MP transparency dossier
│   │   │   ├── SyncLogsView.jsx    # Audit logs and governance disclosure
│   │   │   └── ...
│   │   ├── lib/                    # cn() utility + INR/percentage formatting
│   │   ├── App.jsx                 # Main stateful application
│   │   └── index.css               # shadcn design tokens (Tailwind v4) + glass system
│   ├── components.json             # shadcn CLI configuration
│   └── vite.config.js              # Vite configuration, @ alias & backend proxy
│
└── tests/
    ├── test_risk_engine.py         # Unit tests for models & zero-drift scoring
    └── test_api.py                 # Integration tests for endpoints & RBAC
```

---

## 2b. Public Transparency API (v1.1 additions)

Inspired by civic-transparency platforms, the backend now exposes aggregate, citizen-facing
views alongside the auditor queue (all under `/api`):

| Endpoint | Purpose |
|---|---|
| `GET /api/mps` | Paginated MP directory: sanctioned/disbursed totals, utilization, avg & max risk, high-risk counts. Supports `search`, `state`, `sort_by`, `order`. |
| `GET /api/mps/{mp_name}` | Full MP dossier: tier split, category/status/agency/vendor breakdowns, top-risk works, recent reviews. |
| `GET /api/states` | State-wise aggregation incl. MP coverage counts. |
| `GET /api/states/{state}` | State dossier: tier spread, top MPs, category & agency breakdowns. |
| `GET /api/analytics/categories` | Fund share + risk per work category (chart feed). |
| `GET /api/analytics/status` | Execution-status distribution (chart feed). |
| `GET /api/export/works` | **Open-data CSV export** — streams the filtered works list (same filters as `/works`, `row_limit` capped at 100k). |
| `GET /api/health` | Liveness probe: API + database status, record count. |

Hardening & UX changes shipped with v1.1:
- **Fail-closed RBAC** — missing or unknown `X-User-Role` headers now degrade to *Read-Only Public Tier* instead of escalating to MoSPI Reviewer.
- **Sort-field whitelist** on `/works` and directory endpoints (invalid fields return `400`).
- **GZip middleware** for compressed responses; new `/api/works` filter `work_status`.
- `/api/filter-options` now also returns `statuses` and the full `mps` list.
- Frontend additions: **MP Fund Directory** tab with profile dossiers, category/status charts on the overview, active-filter chips, debounced search, and one-click CSV export of the current filtered view.

### UI system (shadcn/ui + Magic UI)

The dashboard was redesigned on the [shadcn/ui](https://github.com/shadcn-ui/ui) component
system with [Magic UI](https://github.com/magicuidesign/magicui) motion accents, following the
same copy-in component model used by Spectrum UI and shadcnblocks:

- **Toolchain:** `components.json` + `@` path alias + `cn()` utility; Tailwind v4 CSS-first
  design tokens in `src/index.css`.
- **Primitives (`src/components/ui/`):** vendored via `npx shadcn@latest add …` — button,
  badge, card, dialog, input, select, table, tabs, tooltip, progress, skeleton,
  dropdown-menu, separator, sonner (toast), textarea. Radix-powered accessible dialogs
  with focus trapping; review errors surface as toasts instead of `alert()`.
- **Motion (`src/components/magicui/`):** `NumberTicker` (animated stat counters, en-IN
  grouping), `ShimmerButton` (primary CTAs), `AnimatedShinyText` (header tagline),
  `DotPattern` (app backdrop), `BorderBeam` (high-risk metric accent), `BlurFade`
  (list entrance animations).
- To add more components later: `npx shadcn@latest add <component>` (primitives) or copy
  from the Magic UI catalog into `src/components/magicui/`.

### Soft light theme, typography & charts

The visual language follows the **ui-ux-pro-max** design-intelligence skill (installed at
`.zcode/skills/ui-ux-pro-max`), queried for a Government/Public transparency dashboard:

- **Style:** Minimalism & Swiss style + accessible design — soft light surfaces
  (slate-50 `#F8FAFC` background, white cards, slate-200 borders), professional indigo
  primary (`#4F46E5`, 4.7:1 on white), WCAG-safe tint chips for risk tiers.
- **Fonts:** *Outfit* (display headings) + *Work Sans* (body) — the "Geometric Modern"
  pairing from the skill's typography database — with *Fira Code* for tabular figures.
- **Charts:** [Chart.js](https://www.chartjs.org) via `react-chartjs-2`
  (`src/lib/chart.js` holds the shared registration + light-theme tooltip defaults):
  an execution-status doughnut (≤6 slices, largest at 12 o'clock, exact values in the
  legend — per the skill's part-to-whole guidance) and click-to-filter horizontal
  category bars on the Portfolio Overview, plus a per-MP category bar in the profile
  dossier.

---

## 3. How to Install Dependencies

### Prerequisites
- Python 3.11+ (Python 3.14 supported)
- Node.js 18+ and npm

### Backend Installation
```bash
# In the project root:
py -m pip install -r requirements.txt
# Or install core packages:
py -m pip install fastapi uvicorn sqlalchemy psycopg2-binary apscheduler pandas numpy scikit-learn xgboost pytest httpx
```

### Frontend Installation
```bash
cd frontend
npm install
```

---

## 4. How to Configure PostgreSQL

Configure your PostgreSQL database and user:
```sql
CREATE DATABASE mplads_sentinel;
CREATE USER mospi_admin WITH ENCRYPTED PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE mplads_sentinel TO mospi_admin;
```
Set the connection URL in your `.env` file:
```env
DATABASE_URL=postgresql://mospi_admin:secure_password@localhost:5432/mplads_sentinel
```
*(Note: If PostgreSQL is offline, the backend automatically utilizes SQLite fallback `sqlite:///./mplads_sentinel.db` during local development).*

---

## 5. How to Configure Environment Variables

Copy the example template:
```bash
cp .env.example .env
```
Key configuration parameters:
- `DATABASE_URL`: PostgreSQL connection string.
- `API_PREFIX`: `/api`
- `CORS_ORIGINS`: Allowed web client origins.
- Prototype mode uses a local cached MPLADS portal snapshot; there is no scheduler or live network feed.

---

## 6. How to Seed the Database

On application startup, the backend loads the bundled MPLADS website sample when the
`works` table is empty. It reshapes the portal export, runs the five specialist agents,
and upserts the scored work records:
```bash
py -m backend.seeder
```
- **Idempotent:** Safe to run repeatedly; skips execution if records already exist.
- To clear and rebuild the prototype database from the sample, use `py -m backend.seeder --force`.
- To load the larger cached MPLADS portal snapshot instead, use `py -m backend.seeder --force --source live-cache`.
- The cached snapshot contains approximately 420,000 portal rows and 132,000 unique works; it is loaded as one fully rescored snapshot, never mixed with the small sample.
- Existing SQLite files receive required schema additions before loading.

---

## 7. How to Start the Backend

Start the FastAPI application with Uvicorn:
```bash
py -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```
API Documentation will be available at:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

---

## 8. How to Start the Frontend

In a separate terminal:
```bash
cd frontend
npm run dev
```
Open your browser at `http://localhost:5173`.

## 8b. Deploy to Render

See [DEPLOYMENT.md](DEPLOYMENT.md) and the root `render.yaml` blueprint. The
frontend uses `VITE_API_BASE_URL` in deployed environments; leave it unset for
the local Vite proxy.

---

## 9. How to Reload the Prototype Dataset

The reload endpoint is a local prototype operation, not a live sync. It re-reads
`data/mplads_raw_sample.csv`, runs all five agents, and updates the database:

```bash
# Re-score the active cached portal snapshot (MoSPI Reviewer role required)
curl -X POST "http://localhost:8001/api/sync/run" -H "X-User-Role: MoSPI Reviewer"
```

Every reload writes exactly one `sync_logs` entry. No network request is made.

---

## 10. How Prototype Ingestion Works

1. The raw long-format sample is reshaped into one row per work.
2. Financial, timeline, duplicate, vendor, and compliance agents inspect each work
  independently and return scores plus named signals.
3. The coordinator blends those opinions into the final risk score and priority rank.
4. The API and case packet expose the score, evidence factors, agent breakdown, and
  human review record.

The status endpoint reports `mode: prototype` and `is_data_stale: false` because this
dataset is intentionally static. `backend/services/mplads_live.py` is retained as
future integration work and is not imported by the prototype pipeline.

---

## 11. Authoritative Risk Engine & Unified Formula

The risk engine is located at:
```text
model/risk_engine.py
```
It is the **single source of truth** for all risk scoring and case packet generation.

### Prototype scoring:
The coordinator computes a weighted consensus of the five specialist scores, then
combines likelihood with financial impact to produce a 0–100 prioritization score.

- **Likelihood:** Number and severity of independent signals triggered.
- **Impact:** Financial magnitude of public funds involved.
- **Priority:** Elevates cases where risk likelihood intersects with high expenditure.

---

## 12. Multi-Agent Risk Architecture

The prototype does not depend on pretrained model artifacts. The deterministic,
explainable agents live in `model/agents/`:
- **Financial:** cost, utilization, and disbursement anomalies.
- **Timeline:** stalled, implausible, or post-completion activity.
- **Duplicate:** similar descriptions and cross-MP duplicate-work signals.
- **Vendor:** concentration and missing-vendor signals.
- **Compliance:** category, allocation, and evidence checks.

`model/risk_engine.py` is the single facade for scoring and case-packet generation.

---

## 13. How Human Review Works (Phase 5 Feedback Loop)

Authorized auditors submit verification outcomes via:
```http
POST /works/{work_id}/review
```
**Allowed Outcomes:**
- `legitimate`: Valid documentation and physical progress verified.
- `data-quality issue`: Typo, portal date error, or reporting artifact.
- `irregularity`: Substantive procedural, guideline, or cost violation.
- `confirmed fraud`: Fictitious ghost work, embezzlement, or duplicate billing.

Outcomes are recorded in PostgreSQL `review_logs` to build ground-truth labels for future supervised model retraining.

---

## 14. Prototype Limitations

1. The bundled CSV is a sample export, not a live or complete national ledger.
2. Agent scores are audit-prioritization indicators, not findings of fraud.
3. The portal's image column is only an attachment marker; no image bytes are available
  for computer-vision verification.
4. Live portal ingestion, broader production authentication, and model calibration are
  future integration work.

---

## 15. Running the Test Suite

Execute the complete automated test suite verifying model loading, zero scoring drift, API pagination, and RBAC:
```bash
py -m pytest tests -v
```
Output:
```text
tests/test_api.py::test_get_works_pagination_and_priority_order PASSED
tests/test_api.py::test_get_works_filtering PASSED
tests/test_api.py::test_get_case_packet PASSED
tests/test_api.py::test_get_stats_overview PASSED
tests/test_api.py::test_human_review_workflow_and_rbac PASSED
tests/test_risk_engine.py::test_models_load_successfully PASSED
tests/test_risk_engine.py::test_generate_case_packet PASSED
tests/test_risk_engine.py::test_risk_score_consistency_and_zero_drift PASSED

8 passed in ~3s
```
