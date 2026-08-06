# WEE1 Evidence Matrix — App Mockup

A local, full-stack mockup of the **searchable evidence matrix** from the project
primer: a database of biomarkers associated with WEE1-inhibitor response, a web
GUI to search/filter/visualize it, and a documented API to alter, query, and
generate insights from it.

**Everything here uses fabricated dummy data.** The rows tagged `internal_aprea`
are invented placeholders that only exist to demonstrate the confidential-data
segregation flag. No real Aprea data is included.

---

## Architecture

```
                 http (Vite proxy /api -> :8000)
  ┌────────────────────┐        ┌───────────────────────────┐        ┌───────────────┐
  │  React + Recharts  │  --->  │  FastAPI (Python)         │  --->  │  SQLite file  │
  │  (frontend/, :5173)│        │  CRUD + search + insights │        │  (wee1.db)    │
  └────────────────────┘        │  (backend/, :8000)        │        └───────────────┘
                                └───────────────────────────┘
                                       │  auto-docs
                                       ▼
                                 /docs (Swagger UI), /redoc
```

- **Database: SQLite** — zero-config, single file (`backend/wee1.db`), created and
seeded automatically on first launch. Chosen because it "runs locally with
little setup" and needs no server process.
- **Backend: FastAPI + SQLModel** — typed models, automatic interactive API docs.
- **Frontend: Vite + React + Recharts** — search UI + charts.

Why this stack: it's the lightest way to get a real relational DB, a documented
HTTP API, and a modern React UI running locally with two commands.

---



## Quickstart (Windows PowerShell)

You need **Python 3.10+** and **Node 18+**. Open **two terminals**.

### Terminal 1 — backend

```powershell
cd "Work for julie\wee1-evidence-app\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend is now at **[http://localhost:8000](http://localhost:8000)**, interactive docs at
**[http://localhost:8000/docs](http://localhost:8000/docs)**. On first run it creates `wee1.db` and seeds ~220
dummy rows.

### Terminal 2 — frontend

```powershell
cd "Work for julie\wee1-evidence-app\frontend"
npm install
npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)**.

> macOS/Linux: identical, except activate the venv with `source .venv/bin/activate`.



### Reset the database

Stop the backend, delete `backend/wee1.db`, and restart — it re-seeds fresh.

### Local config (optional)

Local dev is zero-config: **auth is off** and storage is the SQLite file. Both are
controlled by environment variables (12-factor), so nothing changes in code between
local and production. Copy `backend/.env.example` → `backend/.env` and/or
`frontend/.env.example` → `frontend/.env` only if you want to exercise auth or
Postgres locally. Leaving them unset keeps the two-command quickstart above.

---



## Using the GUI

Two tabs:

1. **Evidence Explorer** — free-text search (compound / alias / biomarker /
  indication / citation), 13 filter dropdowns mapped 1:1 to the data-dictionary
   categorical fields, a `max p-value` numeric filter, sortable columns
   (click a header), pagination, per-row delete, and an **+ Add evidence** form
   that writes through the API.
2. **Insights & Ranking** — summary cards, a **candidate-biomarker ranking** bar
  chart (composite evidence score), an **effect-size vs significance** volcano
   scatter, **evidence composition** pies (source type + sensitive/resistant),
   and the **indication × regimen landscape** heatmap.

The header toggle **Include Aprea confidential rows** flows through every query
and every insight, so you can see the public-only view vs the combined view — the
mechanism for keeping confidential data segregated.

---



## API reference

Base URL: `http://localhost:8000`. All data endpoints are under `/api`.
Full interactive schema (try requests in the browser): `/docs`.

> **Auth in production:** when `REQUIRE_AUTH=true`, every `/api/*` request needs an
> `Authorization: Bearer <google-id-token>` header from a verified `@aprea.com`
> user; otherwise it returns `401`/`403`. Locally auth is off, so the examples
> below work as-is. `/` and `/healthz` are always public (for health checks).

### ACCESS — read / search


| Method | Path                 | Purpose                                                               |
| ------ | -------------------- | --------------------------------------------------------------------- |
| GET    | `/api/evidence`      | Search/filter/sort/paginate. Returns `{total, limit, offset, items}`. |
| GET    | `/api/evidence/{id}` | Fetch one row.                                                        |
| GET    | `/api/vocab`         | Distinct values per categorical field (powers filter dropdowns).      |


`GET /api/evidence` query parameters:

- `q` — free-text across compound/alias/biomarker/indication/citation/combo_partner.
- **Exact-match filters** — `compound`, `biomarker_name`, `biomarker_type`,
`indication`, `model_type`, `source_type`, `direction`, `treatment_setting`,
`predictive_vs_prognostic`, `wee1_specific_vs_combo`, `baseline_vs_pd`,
`reproducibility`, `evidence_tier`, `is_monotherapy`, `is_aprea_confidential`.
- **Range/flags** — `max_p_value`, `min_year`, `include_confidential` (default true).
- **Paging/sort** — `limit` (1–500, default 50), `offset`, `sort_by`
(`composite_relevance` default, or a column name), `sort_dir` (`asc`/`desc`).



### ALTER — create / update / delete


| Method | Path                 | Purpose                                                       |
| ------ | -------------------- | ------------------------------------------------------------- |
| POST   | `/api/evidence`      | Create one row. Body = evidence object (see data dictionary). |
| PATCH  | `/api/evidence/{id}` | Partial update (only provided fields change).                 |
| DELETE | `/api/evidence/{id}` | Delete a row.                                                 |
| POST   | `/api/evidence/bulk` | Insert many rows (e.g. output of an ingestion script).        |




### INSIGHTS — aggregations


| Method | Path                                 | Returns                                                     |
| ------ | ------------------------------------ | ----------------------------------------------------------- |
| GET    | `/api/insights/summary`              | Headline counts (entries, biomarkers, % predictive, ...).   |
| GET    | `/api/insights/composition`          | Counts by source type / model type / tier / biomarker type. |
| GET    | `/api/insights/biomarker-ranking`    | Ranked biomarkers with composite evidence score.            |
| GET    | `/api/insights/indication-landscape` | Indication × compound grid of sensitivity.                  |
| GET    | `/api/insights/volcano`              | Per-row effect size vs -log10(p).                           |


All insight endpoints accept `include_confidential` (bool).

### Example: Python client

```python
import requests
BASE = "http://localhost:8000"

# 1) ACCESS — every strongly-significant CCNE1 result in ovarian cancer
r = requests.get(f"{BASE}/api/evidence", params={
    "biomarker_name": "CCNE1 amplification",
    "indication": "High-grade serous ovarian",
    "max_p_value": 0.01,
    "include_confidential": False,   # public-only view
    "sort_by": "effect_size", "sort_dir": "desc",
})
print(r.json()["total"], "rows")

# 2) ALTER — add a new observation
new_row = {
    "source_type": "peer_reviewed",
    "citation": "Smith et al. 2025",
    "compound": "azenosertib", "alias": "ZN-c3",
    "indication": "Uterine serous carcinoma", "model_type": "patient",
    "biomarker_name": "CCNE1 amplification", "biomarker_type": "cnv",
    "response_metric": "ORR", "response_value": 42.0, "units": "%",
    "direction": "sensitive", "effect_size": 0.55, "effect_size_type": "hazard_ratio",
    "p_value": 0.003, "predictive_vs_prognostic": "predictive",
    "reproducibility": "multi_dataset", "evidence_tier": "clinical",
}
created = requests.post(f"{BASE}/api/evidence", json=new_row).json()
print("created id", created["id"])

# 3) INSIGHTS — ranked candidate biomarkers
ranking = requests.get(f"{BASE}/api/insights/biomarker-ranking").json()
for row in ranking[:5]:
    print(row["biomarker_name"], row["composite_score"])
```



### Example: curl

```bash
curl "http://localhost:8000/api/evidence?q=CCNE1&max_p_value=0.05&limit=5"
curl "http://localhost:8000/api/insights/biomarker-ranking"
```

---



## Deployment (production)

The app is built to deploy as three pieces, each configured entirely through
environment variables:

```
  Browser (@aprea.com)
      │  Google Sign-In → ID token
      ▼
  GitHub Pages (static React)            Google Cloud Run (FastAPI, container)
  omri-shavit.github.io/aprea/...   ──►   verifies the ID token on every /api call
                                             │
                                             ▼
                                       Cloud SQL (Postgres)
```

**Security model (why this is the "correct" setup).** The login screen only
decides what the UI shows — it can't protect anything on its own, because anyone
can call the API directly. Real enforcement is on the backend: every `/api/*`
route verifies the Google-issued ID token's signature/expiry/audience against
Google's public keys and requires a verified `@aprea.com` email. The frontend
client id and the backend `GOOGLE_CLIENT_ID` **must be the same** OAuth Web
client id (that's the token's audience).

### Prerequisites you (the human) must set up

These require your Google/GitHub accounts, so I can't do them for you:

1. **Google Cloud project** — create one (e.g. `aprea-wee1`) and install the
   [`gcloud` CLI](https://cloud.google.com/sdk/docs/install). Then:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud services enable run.googleapis.com sqladmin.googleapis.com \
       artifactregistry.googleapis.com cloudbuild.googleapis.com
   ```
2. **OAuth 2.0 Web client id** — APIs & Services → Credentials → *Create
   credentials* → *OAuth client ID* → **Web application**. Under *Authorized
   JavaScript origins* add `https://omri-shavit.github.io`. Copy the client id
   (looks like `xxxx.apps.googleusercontent.com`). If `aprea.com` is a Google
   Workspace domain, restrict the OAuth consent screen to *Internal*.
3. **GitHub repo** named **`aprea`** under the `omri-shavit` account, with the
   contents of this `wee1-evidence-app/` folder at its root. Enable Pages
   (Settings → Pages → *Deploy from a branch* → `gh-pages` / `root`).

### 1. Backend → Cloud Run + Cloud SQL (Postgres)

```bash
# Create a Postgres instance, database, and user (one-time)
gcloud sql instances create wee1-db --database-version=POSTGRES_15 \
    --tier=db-f1-micro --region=us-central1
gcloud sql databases create wee1 --instance=wee1-db
gcloud sql users create wee1_app --instance=wee1-db --password='CHOOSE_A_STRONG_PASSWORD'

# The instance connection name, e.g. YOUR_PROJECT_ID:us-central1:wee1-db
gcloud sql instances describe wee1-db --format='value(connectionName)'

# Deploy the container straight from backend/ source
cd backend
gcloud run deploy wee1-evidence-api \
    --source . --region=us-central1 --allow-unauthenticated \
    --add-cloudsql-instances=INSTANCE_CONNECTION_NAME \
    --set-env-vars=REQUIRE_AUTH=true,ALLOWED_EMAIL_DOMAIN=aprea.com \
    --set-env-vars=GOOGLE_CLIENT_ID=YOUR_OAUTH_CLIENT_ID \
    --set-env-vars=ALLOWED_ORIGINS=https://omri-shavit.github.io \
    --set-env-vars='DATABASE_URL=postgresql+psycopg2://wee1_app:CHOOSE_A_STRONG_PASSWORD@/wee1?host=/cloudsql/INSTANCE_CONNECTION_NAME'
```

> `--allow-unauthenticated` here means Cloud Run's own IAM won't block requests;
> access is instead enforced by our in-app `@aprea.com` token check, which is what
> lets browsers hit it directly. Prefer keeping the DB password in **Secret
> Manager** (`--set-secrets=DATABASE_URL=wee1-db-url:latest`) rather than inline.
> On first boot the app auto-creates tables and seeds the dummy rows into Postgres.

Note the service URL it prints (e.g. `https://wee1-evidence-api-xxxx-uc.a.run.app`).

### 2. Frontend → GitHub Pages (automated)

In the `aprea` repo, set **Settings → Secrets and variables → Actions →
Variables** (repo *Variables*, not secrets — they're baked into a public bundle):

- `VITE_API_BASE_URL` = the Cloud Run URL from step 1
- `VITE_GOOGLE_CLIENT_ID` = your OAuth client id

Push to `main`. The included workflow (`.github/workflows/deploy-frontend.yml`)
builds with `VITE_BASE=/aprea/searchable-wee1-inhibitor-database/` and publishes
into that subfolder of the `gh-pages` branch. The app goes live at:

**`https://omri-shavit.github.io/aprea/searchable-wee1-inhibitor-database/`**

### Order of operations & gotchas

- Deploy the **backend first** — you need its URL for `VITE_API_BASE_URL`.
- The OAuth client's *Authorized JavaScript origins* must include
  `https://omri-shavit.github.io`, or Google Sign-In silently fails.
- `ALLOWED_ORIGINS` on Cloud Run must include `https://omri-shavit.github.io`, or
  the browser blocks the cross-origin API calls (CORS).
- Cloud SQL `db-f1-micro` is the cheapest tier; for a pure demo you can instead
  skip Cloud SQL and run SQLite by omitting `DATABASE_URL` and `--add-cloudsql-instances`
  — but data resets whenever Cloud Run recycles the instance, so it's demo-only.

---

## Project layout

```
wee1-evidence-app/
├── README.md
├── DATA_DICTIONARY.md        # authoritative schema: every field, type, units, allowed values
├── .github/workflows/
│   └── deploy-frontend.yml   # CI: build + publish frontend to GitHub Pages
├── backend/
│   ├── main.py               # FastAPI app: protected /api router + public health
│   ├── auth.py               # Google ID-token verification + @aprea.com gate
│   ├── models.py             # SQLModel table + request/response schemas
│   ├── database.py           # env-driven engine (SQLite local / Postgres prod)
│   ├── seed.py               # deterministic correlated dummy-data generator
│   ├── insights.py           # analytics: ranking, landscape, composition, volcano
│   ├── Dockerfile            # container image for Cloud Run
│   ├── .dockerignore
│   ├── .env.example          # REQUIRE_AUTH / GOOGLE_CLIENT_ID / DATABASE_URL / ...
│   ├── requirements.txt
│   └── wee1.db               # created at runtime (git-ignored)
└── frontend/
    ├── package.json
    ├── vite.config.js        # dev proxy /api -> :8000; base path from VITE_BASE
    ├── index.html            # loads Google Identity Services
    ├── .env.example          # VITE_API_BASE_URL / VITE_GOOGLE_CLIENT_ID / ...
    └── src/
        ├── App.jsx           # auth gate + tabs
        ├── auth.js           # token storage + @aprea.com domain check
        ├── api.js            # fetch wrapper: env base URL + bearer token + 401
        ├── styles.css
        └── components/
            ├── Login.jsx           # "Sign in with Google" landing page
            ├── Explorer.jsx        # search + filters + table + delete
            ├── AddEvidenceForm.jsx # POST /api/evidence
            └── Insights.jsx        # charts
```

---



## How to extend it toward the real project

- **Schema**: `DATA_DICTIONARY.md` is the contract. Add a field there first, then to
`models.py`, then it flows through the API and filters automatically.
- **Ingestion**: replace `seed.py` with real ETL that pulls from ClinicalTrials.gov,
PubMed, DepMap, etc. (see the primer's resource guide), normalizes onto the
controlled vocabularies, and calls `POST /api/evidence/bulk`.
- **Ranking**: the composite score is a transparent heuristic in `insights.py` —
adjust the weights (`TIER_WEIGHT`, `REPRO_WEIGHT`, `SOURCE_WEIGHT`) or swap in a
fitted model.
- **Confidential data**: keep the `is_aprea_confidential` flag rigorous; the
`include_confidential` parameter already segregates it end-to-end.

