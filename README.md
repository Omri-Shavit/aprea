# DDR Evidence Matrix

The **searchable evidence matrix** from the project brief: a database of
biomarkers associated with response to **DNA-damage-response inhibitors** (WEE1,
ATR, ATM, CHK1/2, DNA-PK, PARP, PKMYT1, POLQ, USP1, DYRK1A/B and others), a web
GUI to search, filter and visualize it, and a documented API to query it and
generate insights.

**The data is real and public.** ~50k evidence rows harvested from
ClinicalTrials.gov and GDSC, plus a curated dictionary of ~84 DDR agents. Every
row links back to its source trial, dataset or publication. No Aprea
confidential data is included, and the schema currently assumes all data is
public.

**The API is read-only.** Rows enter the database only through the curation
pipeline (`ddr_scavenger/` → `backend/ingest.py`), never through the web app.
See [Altering the data](#altering-the-data).

---

## Architecture

```
                 http (Vite proxy /api -> :8000)
  ┌────────────────────┐        ┌───────────────────────────┐        ┌───────────────┐
  │  React + Recharts  │ ─read─▶│  FastAPI (Python)         │ ─read─▶│  SQLite file  │
  │  (frontend/, :5173)│        │  search + insights        │        │  (wee1.db)    │
  └────────────────────┘        │  (backend/, :8000)        │        └───────────────┘
                                └───────────────────────────┘                ▲
                                       │  auto-docs                          │ write
                                       ▼                                     │
                                 /docs (Swagger UI), /redoc      ddr_scavenger/ → ingest.py
```

- **Database: SQLite** — zero-config, single file (`backend/wee1.db`), created on
first launch and loaded from `backend/data/*.json`. Chosen because it "runs
locally with little setup" and needs no server process. Production swaps in Cloud
SQL Postgres via `DATABASE_URL` with no code change.
- **Backend: FastAPI + SQLModel** — typed models, automatic interactive API docs.
- **Frontend: Vite + React + Recharts** — search UI + charts.

Note the one-way arrows: the web app can only read. The single writer is
`ingest.py`, run deliberately from a terminal, which keeps every row traceable
to a harvested source.

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
**[http://localhost:8000/docs](http://localhost:8000/docs)**. On first run it creates `wee1.db` and loads the
curated data from `backend/data/` (~84 compounds, ~50k evidence rows); later runs
see the populated tables and skip the load.

> `backend/data/*.json` is git-ignored (the evidence file alone is ~84 MB), so a
> fresh clone starts empty. Regenerate it with the pipeline in `ddr_scavenger/`,
> or point `DATABASE_URL` at an already-populated database.

### Terminal 2 — frontend

```powershell
cd "Work for julie\wee1-evidence-app\frontend"
npm install
npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)**.

> macOS/Linux: identical, except activate the venv with `source .venv/bin/activate`.



### Reset the database

Stop the backend and run `python ingest.py --recreate` from `backend/`, which
drops the tables and reloads them from `data/`. Use this after any schema change;
a plain `ingest.py` sees existing rows and skips. Deleting `backend/wee1.db` and
restarting works too.

### Local config (optional)

Local dev is zero-config: **auth is off** and storage is the SQLite file. Both are
controlled by environment variables (12-factor), so nothing changes in code between
local and production. Copy `backend/.env.example` → `backend/.env` and/or
`frontend/.env.example` → `frontend/.env` only if you want to exercise auth or
Postgres locally. Leaving them unset keeps the two-command quickstart above.

---



## Using the GUI

Three tabs:

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

> **Auth:** when `REQUIRE_AUTH=true`, every `/api/*` request needs an
> `Authorization: Bearer <google-id-token>` header from a verified `@aprea.com`
> user; otherwise it returns `401`/`403`. Auth is currently off both locally and
> in production, so the examples below work as-is. `/`, `/health` and `/healthz`
> are always public (for health checks). Both health paths exist on purpose:
> Google Front End reserves some `/*z` paths, so `/healthz` can 404 in front of
> Cloud Run even though FastAPI serves it.

### ACCESS — read / search


| Method | Path                 | Purpose                                                               |
| ------ | -------------------- | --------------------------------------------------------------------- |
| GET    | `/api/evidence`      | Search/filter/sort/paginate. Returns `{total, limit, offset, items}`. |
| GET    | `/api/evidence/{id}` | Fetch one row.                                                        |
| GET    | `/api/vocab`         | Distinct values per categorical field, plus the cascade maps.         |

`GET /api/vocab` also returns `compounds_by_target` and `combo_partners_by_track`
(driving the dependent dropdowns) and `controlled`, the closed vocabularies from
`vocabulary.py` used as a fallback when the database is empty.

`GET /api/evidence` query parameters:

- `q` — free-text across compound / alias / target / biomarker / indication /
citation / combo_partner / notes.
- **Drug & target** — `target`, `target_family`, `compound`.
- **Cancer type** — `indication`, `indication_category`.
- **Regimen** — `combination_track` (`monotherapy` | `chemotherapy` |
`radiotherapy` | `targeted_agent`), `combo_partner`, `is_monotherapy`, and
`therapy_mode` (`all` | `mono` | `combo`, the segmented control's filter;
`is_monotherapy` wins if both are given).
- **Biomarker & assay** — `biomarker_name`, `biomarker_type`, `biomarker_scope`,
`assay_modality`, `specimen_type`, `specimen_timing`, `perturbation_type`.
- **Evidence & outcome** — `source_type`, `model_type`, `direction`,
`treatment_setting`, `predictive_vs_prognostic`, `target_specific_vs_combo`,
`baseline_vs_pd`, `reproducibility`, `evidence_tier`, `evidence_basis`,
`endpoint_class`, `response_metric`.
- **Ranges** — `max_p_value`, `min_year`.
- **Paging/sort** — `limit` (1–500, default 50), `offset`, `sort_by`
(`composite_relevance` default, or a column name), `sort_dir` (`asc`/`desc`).

### DICTIONARY — the controlled drug list

| Method | Path                  | Purpose                                        |
| ------ | --------------------- | ---------------------------------------------- |
| GET    | `/api/compounds`      | The DDR agents, ordered by target then name.   |
| GET    | `/api/compounds/{id}` | Fetch one agent.                               |

Parameters: `target`, `target_family`, `q` (over canonical name / aliases /
developer), and `include_tool_compounds` (default true; set false to hide
preclinical probes).



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


| Method | Path                                 | Returns                                                              |
| ------ | ------------------------------------ | -------------------------------------------------------------------- |
| GET    | `/api/insights/summary`              | Headline counts (rows, targets, biomarkers, clinical vs preclinical). |
| GET    | `/api/insights/composition`          | Counts by target, regimen track, indication category, perturbation.   |
| GET    | `/api/insights/biomarker-ranking`    | Ranked biomarkers with the eight-dimension composite score.           |
| GET    | `/api/insights/indication-landscape` | Indication × compound (or × target) grid of sensitivity.              |
| GET    | `/api/insights/volcano`              | Per-row effect size vs -log10(p).                                     |
| GET    | `/api/insights/target-overview`      | Per-target rollups (rows, drugs, biomarkers, top biomarkers).         |


Every insight endpoint accepts the same optional scoping filters — `target`,
`combination_track`, `indication_category`, `evidence_tier` and
`perturbation_type` — so any panel can be recomputed for one slice of the matrix.
`indication-landscape` additionally accepts `by` (`compound` or `target`).

Results are memoized in-process (see `insight_cache.py`), so repeated unscoped
requests over all ~50k rows stay fast.

### Example: Python client

```python
import requests
BASE = "http://localhost:8000"

# 1) ACCESS - strongly-significant CCNE1 results for WEE1 monotherapy
r = requests.get(f"{BASE}/api/evidence", params={
    "target": "WEE1",
    "biomarker_name": "CCNE1 amplification",
    "therapy_mode": "mono",
    "max_p_value": 0.01,
    "sort_by": "effect_size", "sort_dir": "desc",
})
print(r.json()["total"], "rows")

# 2) DICTIONARY - the controlled list of agents for one target
drugs = requests.get(f"{BASE}/api/compounds", params={"target": "WEE1"}).json()
print([d["canonical_name"] for d in drugs])

# 3) INSIGHTS - ranked candidate biomarkers, scoped to one target
ranking = requests.get(f"{BASE}/api/insights/biomarker-ranking",
                       params={"target": "WEE1"}).json()
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
> **`REQUIRE_AUTH=false`** (current default) leaves the API readable by anyone
> with the URL — acceptable only because every row is public data and the API
> exposes no write routes. Set `REQUIRE_AUTH=true` once Microsoft Entra ID login
> is wired, and before any confidential data is loaded.
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

**Loading data into Cloud SQL.** Startup ingestion is opt-in (`INGEST_ON_STARTUP`,
default false when `DATABASE_URL` is set), because pushing ~50k rows during boot
risks tripping Cloud Run's startup probe. Load the data with a one-off Cloud Run
job on the same VPC/Cloud SQL connection instead, so the database never has to be
exposed publicly:

```bash
gcloud run jobs create ddr-ingest --source . --region=us-central1 \
    --add-cloudsql-instances=INSTANCE_CONNECTION_NAME \
    --update-secrets=DATABASE_URL=wee1-db-url:latest \
    --command=python --args='ingest.py','--recreate'
gcloud run jobs execute ddr-ingest --region=us-central1 --wait
```

Pass each argument separately as shown; a single comma-joined string is read as
one filename. Use `--recreate` whenever the schema has changed, since a plain
run finds the existing rows and skips.

Note the service URL it prints (e.g. `https://wee1-evidence-api-xxxx-uc.a.run.app`).

### 2. Frontend → GitHub Pages (automated)

In the `aprea` repo, set **Settings → Secrets and variables → Actions →
Variables** (repo *Variables*, not secrets — they're baked into a public bundle):

- `VITE_API_BASE_URL` = the Cloud Run URL from step 1

Auth is **off** in production builds (`VITE_REQUIRE_AUTH=false` in the workflow).
No login screen until Microsoft Entra ID is added later.

Push to `main`. Any change under `frontend/` triggers the workflow, which builds
with `VITE_BASE=/aprea/searchable-wee1-inhibitor-database/` and publishes into
that subfolder of the `gh-pages` branch. It can also be run by hand from
**Actions → Deploy frontend → Run workflow**. The app goes live at:

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
├── DB_progress_update_8_20_2026.md  # status report: sources, quality, scoring, next steps
├── .github/workflows/
│   └── deploy-frontend.yml   # CI: build + publish frontend to GitHub Pages
├── ddr_scavenger/            # harvest pipeline (writes backend/data/*.json)
│   ├── ddr_config.py         # drug dictionary + biomarker regex vocabulary
│   ├── harvest_ddr.py        # ClinicalTrials.gov + GDSC collection
│   ├── build_evidence.py     # normalize onto the Evidence schema
│   └── verify.py             # sanity checks on the generated data
├── backend/
│   ├── main.py               # FastAPI app: read-only /api router + public health
│   ├── auth.py               # Google ID-token verification + @aprea.com gate
│   ├── models.py             # SQLModel tables (Compound, Evidence) + read schemas
│   ├── database.py           # env-driven engine (SQLite local / Postgres prod)
│   ├── ingest.py             # the only writer: loads data/*.json into the DB
│   ├── vocabulary.py         # controlled vocabularies (targets, tracks, endpoints)
│   ├── insights.py           # analytics: ranking, landscape, composition, volcano
│   ├── insight_cache.py      # versioned in-process cache for the insight endpoints
│   ├── tests/                # insight field-contract + cache tests (pytest)
│   ├── data/                 # generated evidence + compounds JSON (git-ignored)
│   ├── Dockerfile            # container image for Cloud Run
│   ├── .dockerignore
│   ├── .gcloudignore         # keeps .venv/tests out of the Cloud Build upload
│   ├── .env.example          # REQUIRE_AUTH / GOOGLE_CLIENT_ID / DATABASE_URL / ...
│   ├── requirements.txt
│   ├── requirements-dev.txt  # pytest
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
        ├── format.js         # shared display helpers (counts, nulls, EMPTY)
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

