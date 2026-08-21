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
   indication / citation / target / notes), cascading **Target → Drug**
   dropdowns, a monotherapy/combination therapy-mode control, grouped secondary
   filters mapped 1:1 to the data-dictionary categorical fields, `max p-value`
   and `from year` numeric filters, sortable columns (click a header), and
   pagination. The view is read-only.
2. **Drug Dictionary** — the controlled list of DDR agents, grouped by target,
   with aliases, developer, clinical stage, selectivity and known off-target
   activity.
3. **Insights & Ranking** — summary cards, a **candidate-biomarker ranking** bar
   chart (eight-dimension composite score), an **effect-size vs significance**
   volcano scatter, **evidence composition** pies, and the **indication ×
   regimen landscape** heatmap. Every panel is recomputed for the selected
   target.

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



### Altering the data

The API is **read-only**. There are no create, update or delete routes, and the
GUI has no editing controls. Rows enter the database one way only: the curation
pipeline writes `backend/data/*.json`, and `python ingest.py` loads it.

```bash
cd backend
python ingest.py             # load; skips if the tables already hold rows
python ingest.py --recreate  # drop and rebuild the tables first (schema changes)
```

This keeps a single reviewable path into the evidence base, so every row stays
traceable to a harvested source rather than to whoever had the URL open. Write
access should return only behind real authentication (see `auth.py`), at which
point `insight_cache.bump_version()` has to be called from each write path.




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

# 2) DICTIONARY - the controlled list of agents for one target
drugs = requests.get(f"{BASE}/api/compounds", params={"target": "WEE1"}).json()
print([d["canonical_name"] for d in drugs])

# 3) INSIGHTS - ranked candidate biomarkers
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

> **Current status: live.** Both pieces are deployed and wired together end-to-end:
> - **Backend** (FastAPI on Cloud Run + Cloud SQL Postgres):
>   [`https://wee1-evidence-api-57264445243.us-central1.run.app`](https://wee1-evidence-api-57264445243.us-central1.run.app)
> - **Frontend** (React on GitHub Pages):
>   [`https://omri-shavit.github.io/aprea/searchable-wee1-inhibitor-database/`](https://omri-shavit.github.io/aprea/searchable-wee1-inhibitor-database/)
>
> `REQUIRE_AUTH=false` (no login wired up yet), and the Cloud SQL DB password lives
> in **Secret Manager** (`wee1-db-url` secret, mounted as the `DATABASE_URL` env var
> on Cloud Run) rather than as a plaintext env var. The sections below are the
> from-scratch setup steps that produced this state — useful if you need to
> redeploy, rotate credentials, or stand up a second environment.

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

# Put the DB connection string in Secret Manager instead of a plain env var
# (avoid the raw value ending up in shell history — pipe it in or use a temp
# file you delete right after)
gcloud services enable secretmanager.googleapis.com
echo -n 'postgresql+psycopg2://wee1_app:CHOOSE_A_STRONG_PASSWORD@/wee1?host=/cloudsql/INSTANCE_CONNECTION_NAME' \
    | gcloud secrets create wee1-db-url --data-file=-

# Deploy the container straight from backend/ source
cd backend
gcloud run deploy wee1-evidence-api \
    --source . --region=us-central1 --allow-unauthenticated \
    --add-cloudsql-instances=INSTANCE_CONNECTION_NAME \
    --set-env-vars=REQUIRE_AUTH=false \
    --set-env-vars=ALLOWED_ORIGINS=https://omri-shavit.github.io \
    --update-secrets=DATABASE_URL=wee1-db-url:latest

# Grant the Cloud Run runtime service account access to the secret (one-time;
# find the SA via `gcloud run services describe wee1-evidence-api
# --region=us-central1 --format='value(spec.template.spec.serviceAccountName)'`
# — empty means it's the default compute SA, PROJECT_NUMBER-compute@developer.gserviceaccount.com)
gcloud secrets add-iam-policy-binding wee1-db-url \
    --member='serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com' \
    --role='roles/secretmanager.secretAccessor'
```

> `--allow-unauthenticated` means Cloud Run IAM won't block browser requests.
> **`REQUIRE_AUTH=false`** (current default) leaves the API open — fine for the
> dummy-data demo. Set `REQUIRE_AUTH=true` once Microsoft Entra ID login is wired.
> The DB password is kept in **Secret Manager** (`wee1-db-url`, mounted as the
> `DATABASE_URL` env var via `--update-secrets`) rather than as a plaintext
> `--set-env-vars` value — this is the actual production setup, not just a
> suggestion. To rotate the password later: `gcloud sql users set-password
> wee1_app --instance=wee1-db --password=NEW_PASSWORD`, then `gcloud secrets
> versions add wee1-db-url --data-file=-` with the updated connection string,
> then re-run the `gcloud run deploy`/`update` command so Cloud Run resolves the
> new `:latest` version into a fresh revision (Cloud Run pins the secret version
> at revision-creation time, so simply adding a secret version doesn't affect
> already-running revisions).
> On first boot the app auto-creates tables and seeds the dummy rows into Postgres.

Note the service URL it prints (e.g. `https://wee1-evidence-api-xxxx-uc.a.run.app`).

### 2. Frontend → GitHub Pages (automated)

In the `aprea` repo, set **Settings → Secrets and variables → Actions →
Variables** (repo *Variables*, not secrets — they're baked into a public bundle):

- `VITE_API_BASE_URL` = the Cloud Run URL from step 1

Auth is **off** in production builds (`VITE_REQUIRE_AUTH=false` in the workflow).
No login screen until Microsoft Entra ID is added later.

Push to `main`.
builds with `VITE_BASE=/aprea/searchable-wee1-inhibitor-database/` and publishes
into that subfolder of the `gh-pages` branch. The app goes live at:

**`https://omri-shavit.github.io/aprea/searchable-wee1-inhibitor-database/`**

#### Self-hosted runner on GCP (if GitHub-hosted runners fail)

GitHub's shared runners can queue for a long time or fail with internal errors.
This repo's deploy workflow uses a **self-hosted runner** on a small GCP VM instead.

**One-time setup (~10 min):**

1. **Create the VM** (PowerShell, from `scripts/`):
   ```powershell
   .\create-gcp-runner-vm.ps1
   ```
2. **Get a registration token** — GitHub → `Omri-Shavit/aprea` → **Settings** →
   **Actions** → **Runners** → **New self-hosted runner** → **Linux** → copy token
   (expires in ~1 hour).
3. **SSH into the VM and install the runner:**
   ```bash
   gcloud compute ssh github-actions-runner --zone=us-central1-a --project=wee1-inhibitor-database

   curl -fsSL https://raw.githubusercontent.com/Omri-Shavit/aprea/main/scripts/setup-gcp-actions-runner.sh -o setup.sh
   chmod +x setup.sh
   sudo ./setup.sh YOUR_REGISTRATION_TOKEN
   ```
4. Confirm the runner shows **Idle** under **Settings → Actions → Runners**.
5. **Actions → Deploy frontend to GitHub Pages → Run workflow**.

The VM (`e2-small`, ~$12/mo if always on) only runs when a job is queued. Stop it
when not needed: `gcloud compute instances stop github-actions-runner --zone=us-central1-a`

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
│   ├── ingest.py             # the only writer: loads data/*.json into the DB
│   ├── vocabulary.py         # controlled vocabularies (targets, tracks, endpoints)
│   ├── insights.py           # analytics: ranking, landscape, composition, volcano
│   ├── insight_cache.py      # versioned in-process cache for the insight endpoints
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
            ├── Explorer.jsx        # search + cascading filters + table
            ├── Compounds.jsx       # drug dictionary
            └── Insights.jsx        # charts
```

---



## How to extend it toward the real project

- **Schema**: `DATA_DICTIONARY.md` is the contract. Add a field there first, then to
`models.py`, then it flows through the API and filters automatically.
- **Ingestion**: extend `ddr_scavenger/` to cover more sources (DepMap PRISM, CTRP,
PharmacoDB, GEO), normalize onto `vocabulary.py`, and reload with
`python ingest.py --recreate`.
- **Ranking**: the composite score is a transparent heuristic in `insights.py`.
Adjust the eight dimension weights (`SCORE_WEIGHTS`) or swap in a fitted model.
- **Write access**: if privileged editing is needed, put it behind Microsoft Entra
ID in `auth.py` and gate the routes on the verified user, rather than reopening
the endpoints to anyone who can reach the service.

