"""
DDR Evidence Matrix API
=======================

A FastAPI service implementing the "searchable evidence matrix" from the
program brief, covering **all DNA-damage-response targets** (WEE1, ATR, ATM,
CHK1, DNA-PK, PARP, PKMYT1, POLQ, USP1, DYRK1A/B, ...). Three capabilities:

  1. ACCESS    -> GET /api/evidence                 (search/filter/sort/paginate)
  2. DICTIONARY-> GET /api/compounds                (the controlled drug dictionary)
  3. INSIGHTS  -> GET /api/insights/*               (aggregations & rankings)

`GET /api/vocab` returns the distinct values present in the data plus the
cascade maps (`compounds_by_target`, `combo_partners_by_track`) that drive the
frontend's dependent dropdowns.

**This API is read-only.** There are no create/update/delete routes: the
database is altered only by the curation pipeline, via `python ingest.py`
against `backend/data/*.json`. That keeps a single, reviewable path into the
data - every row traceable to a harvested source - instead of letting anyone
with the URL edit the evidence base. Restoring write access means putting it
behind real authentication first (see `auth.py`), not simply re-adding routes.

All /api/* routes are protected by `require_user` (Google Sign-In, @aprea.com).
Auth is enforced only when REQUIRE_AUTH=true, so local dev stays zero-config.

Storage is chosen by DATABASE_URL (SQLite locally, Cloud SQL Postgres in prod).
The database ships EMPTY: real reference data is loaded at startup by
`ingest.load_reference_data()` if that module and its JSON files are present.
There is no dummy/synthetic seed data.

Interactive, auto-generated API docs: /docs (Swagger), /redoc (ReDoc).

Run locally:
    uvicorn main:app --reload
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

try:
    # Optional: load a local .env for convenience (no-op if not installed / no file)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_
from sqlmodel import Session, select

import insight_cache
import insights as insights_mod
import vocabulary as vocab
from auth import ALLOWED_EMAIL_DOMAIN, REQUIRE_AUTH, require_user
from database import get_session, init_db
from models import Compound, CompoundRead, Evidence, EvidenceRead

log = logging.getLogger("uvicorn.error")


def _ingest_on_startup() -> bool:
    """Whether boot should load the reference data if the tables are empty.

    Defaults to on for local SQLite (zero-setup: clone, run, get a full
    database) and off when DATABASE_URL points at a real server. Loading 50k
    rows into Postgres takes far longer than a container start-up probe allows,
    so a managed deployment would fail its health check while ingesting. There,
    data is loaded once out-of-band with ``python ingest.py`` and the app simply
    serves what it finds. Set INGEST_ON_STARTUP explicitly to override.
    """
    default = "false" if os.getenv("DATABASE_URL") else "true"
    return os.getenv("INGEST_ON_STARTUP", default).strip().lower() in {"1", "true", "yes"}


def _startup() -> None:
    """Create the tables, then optionally load the curated reference data.

    Ingestion is deliberately best-effort: `ingest.py` and the JSON files under
    `backend/data/` are produced by the curation pipeline and may not be
    present in every environment (fresh clone, CI, a reviewer's laptop). An
    empty database is a valid state - every endpoint returns a clean empty
    payload - so a missing ingest module logs a warning and boots anyway.
    `load_reference_data()` is itself idempotent: it no-ops when the tables are
    already populated.
    """
    init_db()
    if not _ingest_on_startup():
        log.info(
            "Skipping start-up ingestion (INGEST_ON_STARTUP is off). Serving the "
            "existing database; load data with `python ingest.py`."
        )
        return
    try:
        from ingest import load_reference_data

        result = load_reference_data()
        log.info("Reference data load: %s", result)
    except (ImportError, FileNotFoundError) as exc:
        log.warning(
            "Reference data not loaded (%s: %s). Starting with the existing database contents.",
            type(exc).__name__,
            exc,
        )
    except Exception as exc:  # pragma: no cover - never block startup on ingest
        log.warning("Reference data load failed (%s: %s). Continuing.", type(exc).__name__, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup()
    yield


app = FastAPI(
    title="DDR Evidence Matrix API",
    version="0.3.0",
    description=__doc__,
    lifespan=lifespan,
)

# CORS: comma-separated origins via env. Defaults to the Vite dev/preview ports.
# In production set ALLOWED_ORIGINS to your GitHub Pages / aprea.com origin.
_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every /api route requires a verified @aprea.com user (when REQUIRE_AUTH=true).
api = APIRouter(prefix="/api", dependencies=[Depends(require_user)])


# --------------------------------------------------------------------------
# Write-side normalization helpers
#
# The matrix is assembled by several curators and by the ingestion pipeline, so
# the API derives the fields it can derive rather than rejecting rows that omit
# them. Every derivation is reversible by supplying the field explicitly.
# --------------------------------------------------------------------------

def _target_rank(target: Optional[str]) -> int:
    """Sort key placing canonical targets in `vocabulary.TARGETS` order, others last."""
    try:
        return vocab.TARGETS.index(target)
    except ValueError:
        return len(vocab.TARGETS)


def _sorted_ci(values) -> List[str]:
    """Case-insensitive A-Z, so 'adavosertib' isn't sorted after 'ZN-c3'."""
    return sorted(values, key=lambda v: (str(v).lower(), str(v)))


def _ordered(values, canonical: List[str]) -> List[str]:
    """Canonical order for the values actually present, then any extras A-Z."""
    present = set(values)
    ranked = [v for v in canonical if v in present]
    extras = _sorted_ci(v for v in present if v not in canonical)
    return ranked + extras


# --------------------------------------------------------------------------
# ACCESS: search / filter / sort / paginate
# --------------------------------------------------------------------------

SORTABLE = {
    # numeric
    "id", "year", "effect_size", "p_value", "q_value", "response_value", "n",
    # text
    "target", "target_family", "compound", "biomarker_name", "biomarker_type",
    "indication", "indication_category", "combination_track", "combo_partner",
    "model_type", "perturbation_type", "source_type", "evidence_tier",
    "evidence_basis", "response_metric", "endpoint_class", "specimen_type",
    "specimen_timing", "assay_modality",
}

# Free-text `q` searches these columns with ILIKE.
_SEARCH_COLUMNS = (
    "compound", "alias", "target", "biomarker_name", "indication", "citation",
    "combo_partner", "notes",
)


@api.get("/evidence", response_model=dict, tags=["access"])
def list_evidence(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(
        None,
        description="Free-text search across compound/alias/target/biomarker/indication/"
        "citation/combo_partner/notes.",
    ),
    target: Optional[str] = None,
    target_family: Optional[str] = None,
    compound: Optional[str] = None,
    biomarker_name: Optional[str] = None,
    biomarker_type: Optional[str] = None,
    biomarker_scope: Optional[str] = None,
    indication: Optional[str] = None,
    indication_category: Optional[str] = None,
    model_type: Optional[str] = None,
    perturbation_type: Optional[str] = None,
    source_type: Optional[str] = None,
    direction: Optional[str] = None,
    treatment_setting: Optional[str] = None,
    predictive_vs_prognostic: Optional[str] = None,
    target_specific_vs_combo: Optional[str] = None,
    baseline_vs_pd: Optional[str] = None,
    reproducibility: Optional[str] = None,
    evidence_tier: Optional[str] = None,
    evidence_basis: Optional[str] = None,
    combination_track: Optional[str] = None,
    combo_partner: Optional[str] = None,
    specimen_type: Optional[str] = None,
    specimen_timing: Optional[str] = None,
    assay_modality: Optional[str] = None,
    endpoint_class: Optional[str] = None,
    response_metric: Optional[str] = None,
    is_monotherapy: Optional[bool] = None,
    therapy_mode: str = Query(
        "all",
        pattern="^(all|mono|combo)$",
        description="Convenience filter backing the UI's mono/combo segmented control. "
        "`is_monotherapy` takes precedence when both are supplied.",
    ),
    max_p_value: Optional[float] = Query(None, description="Keep rows with p_value <= this."),
    min_year: Optional[int] = Query(None, description="Keep rows with year >= this."),
    sort_by: str = Query(
        "composite_relevance",
        description=f"One of {sorted(SORTABLE)} or 'composite_relevance'.",
    ),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Primary programmatic access point. Returns `{total, limit, offset, items}`."""
    stmt = select(Evidence)

    exact = {
        "target": target,
        "target_family": target_family,
        "compound": compound,
        "biomarker_name": biomarker_name,
        "biomarker_type": biomarker_type,
        "biomarker_scope": biomarker_scope,
        "indication": indication,
        "indication_category": indication_category,
        "model_type": model_type,
        "perturbation_type": perturbation_type,
        "source_type": source_type,
        "direction": direction,
        "treatment_setting": treatment_setting,
        "predictive_vs_prognostic": predictive_vs_prognostic,
        "target_specific_vs_combo": target_specific_vs_combo,
        "baseline_vs_pd": baseline_vs_pd,
        "reproducibility": reproducibility,
        "evidence_tier": evidence_tier,
        "evidence_basis": evidence_basis,
        "combination_track": combination_track,
        "combo_partner": combo_partner,
        "specimen_type": specimen_type,
        "specimen_timing": specimen_timing,
        "assay_modality": assay_modality,
        "endpoint_class": endpoint_class,
        "response_metric": response_metric,
        "is_monotherapy": is_monotherapy,
    }
    for field, value in exact.items():
        if value is not None:
            stmt = stmt.where(getattr(Evidence, field) == value)

    # therapy_mode is the coarse UI control; an explicit is_monotherapy wins.
    if is_monotherapy is None and therapy_mode in ("mono", "combo"):
        stmt = stmt.where(Evidence.is_monotherapy == (therapy_mode == "mono"))

    if max_p_value is not None:
        stmt = stmt.where(Evidence.p_value <= max_p_value)
    if min_year is not None:
        stmt = stmt.where(Evidence.year >= min_year)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(*[getattr(Evidence, c).ilike(like) for c in _SEARCH_COLUMNS])
        )

    # total (before pagination)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()

    if sort_by == "composite_relevance":
        # Surface the most statistically significant signals first (small p),
        # breaking ties by larger absolute effect. Much of the real corpus has
        # no p-value at all, so NULLs are explicitly pushed to the end via an
        # `IS NULL` sort key - portable across SQLite and Postgres, unlike
        # NULLS LAST. Note effect sizes mix scales (r vs Cohen's d vs hazard
        # ratio), so p is the safer primary key.
        stmt = stmt.order_by(
            Evidence.p_value.is_(None).asc(),
            Evidence.p_value.asc(),
            Evidence.effect_size.is_(None).asc(),
            func.abs(Evidence.effect_size).desc(),
            Evidence.id.asc(),
        )
    elif sort_by in SORTABLE:
        col = getattr(Evidence, sort_by)
        stmt = stmt.order_by(
            col.is_(None).asc(),
            col.desc() if sort_dir == "desc" else col.asc(),
            Evidence.id.asc(),
        )

    items = session.exec(stmt.offset(offset).limit(limit)).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@api.get("/evidence/{evidence_id}", response_model=EvidenceRead, tags=["access"])
def get_evidence(evidence_id: int, session: Session = Depends(get_session)):
    row = session.get(Evidence, evidence_id)
    if not row:
        raise HTTPException(404, "Evidence row not found")
    return row


# Categorical evidence fields exposed as filter dropdowns.
_VOCAB_FIELDS = [
    "target", "target_family", "compound", "biomarker_name", "biomarker_type",
    "biomarker_scope", "indication", "indication_category", "model_type",
    "perturbation_type", "source_type", "direction", "treatment_setting",
    "predictive_vs_prognostic", "target_specific_vs_combo", "baseline_vs_pd",
    "reproducibility", "evidence_tier", "evidence_basis", "combination_track",
    "combo_partner", "specimen_type", "specimen_timing", "assay_modality",
    "endpoint_class", "response_metric",
]

# Canonical display order per field, where one exists. Fields absent from this
# map are sorted alphabetically.
_VOCAB_ORDER = {
    "target": vocab.TARGETS,
    "target_family": vocab.TARGET_FAMILIES,
    "combination_track": vocab.COMBINATION_TRACKS,
    "indication_category": vocab.INDICATION_CATEGORIES,
    "source_type": vocab.SOURCE_TYPES,
    "model_type": vocab.MODEL_TYPES,
    "perturbation_type": vocab.PERTURBATION_TYPES,
    "biomarker_type": vocab.BIOMARKER_TYPES,
    "biomarker_scope": vocab.BIOMARKER_SCOPES,
    "assay_modality": vocab.ASSAY_MODALITIES,
    "specimen_type": vocab.SPECIMEN_TYPES,
    "specimen_timing": vocab.SPECIMEN_TIMINGS,
    "direction": vocab.DIRECTIONS,
    "evidence_tier": vocab.EVIDENCE_TIERS,
    "reproducibility": vocab.REPRODUCIBILITY,
    "predictive_vs_prognostic": vocab.PREDICTIVE_CLASSES,
    "evidence_basis": vocab.EVIDENCE_BASES,
    "target_specific_vs_combo": vocab.ATTRIBUTION,
    "baseline_vs_pd": vocab.BASELINE_VS_PD,
    "treatment_setting": vocab.TREATMENT_SETTINGS,
    "response_metric": vocab.RESPONSE_METRICS,
    "endpoint_class": vocab.ENDPOINT_CLASSES,
}


@api.get("/vocab", tags=["access"])
def vocabularies(session: Session = Depends(get_session)):
    """Dropdown options for the frontend, derived from the data actually present.

    Returns one key per categorical field (distinct values, canonical order
    where `vocabulary.py` defines one), plus two cascade maps:

      * `compounds_by_target`      - target -> the drugs seen with that target
      * `combo_partners_by_track`  - track  -> the partners seen in that track

    and `controlled`, the full controlled vocabulary from `vocabulary.py`, so
    the add/edit form can offer every allowed value even when the table is
    empty or a value has no rows yet.
    """
    out: Dict[str, Any] = {}
    for field in _VOCAB_FIELDS:
        col = getattr(Evidence, field)
        values = session.exec(select(col).distinct().where(col.is_not(None))).all()
        values = [v for v in values if v not in (None, "")]
        canonical = _VOCAB_ORDER.get(field)
        out[field] = _ordered(values, canonical) if canonical else _sorted_ci(values)

    # Target -> compounds cascade, from the (target, compound) pairs in the data.
    pairs = session.exec(
        select(Evidence.target, Evidence.compound)
        .distinct()
        .where(Evidence.target.is_not(None), Evidence.compound.is_not(None))
    ).all()
    compounds_by_target: Dict[str, set] = {}
    for target_name, compound_name in pairs:
        compounds_by_target.setdefault(target_name, set()).add(compound_name)
    out["compounds_by_target"] = {
        t: _sorted_ci(compounds_by_target[t])
        for t in sorted(compounds_by_target, key=lambda t: (_target_rank(t), t))
    }

    # Track -> combination partners cascade.
    track_pairs = session.exec(
        select(Evidence.combination_track, Evidence.combo_partner)
        .distinct()
        .where(Evidence.combo_partner.is_not(None))
    ).all()
    partners_by_track: Dict[str, set] = {}
    for track, partner in track_pairs:
        if partner:
            partners_by_track.setdefault(track or "unknown", set()).add(partner)
    out["combo_partners_by_track"] = {
        t: _sorted_ci(partners_by_track[t])
        for t in _ordered(partners_by_track, vocab.COMBINATION_TRACKS)
    }

    out["controlled"] = {field: list(values) for field, values in _VOCAB_ORDER.items()}
    return out


# --------------------------------------------------------------------------
# DICTIONARY: the controlled compound table
# --------------------------------------------------------------------------

@api.get("/compounds", response_model=List[CompoundRead], tags=["dictionary"])
def list_compounds(
    session: Session = Depends(get_session),
    target: Optional[str] = Query(None, description="Exact DDR target, e.g. WEE1."),
    target_family: Optional[str] = None,
    q: Optional[str] = Query(None, description="Free-text over canonical_name/aliases/developer."),
    include_tool_compounds: bool = Query(
        True, description="Set false to hide preclinical probes (is_tool_compound)."
    ),
):
    """The drug dictionary, ordered by DDR target (canonical order) then name."""
    stmt = select(Compound)
    if target is not None:
        stmt = stmt.where(Compound.target == target)
    if target_family is not None:
        stmt = stmt.where(Compound.target_family == target_family)
    if not include_tool_compounds:
        stmt = stmt.where(Compound.is_tool_compound == False)  # noqa: E712
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Compound.canonical_name.ilike(like),
                Compound.aliases.ilike(like),
                Compound.developer.ilike(like),
            )
        )
    rows = session.exec(stmt).all()
    return sorted(rows, key=lambda c: (_target_rank(c.target), (c.canonical_name or "").lower()))


@api.get("/compounds/{compound_id}", response_model=CompoundRead, tags=["dictionary"])
def get_compound(compound_id: int, session: Session = Depends(get_session)):
    row = session.get(Compound, compound_id)
    if not row:
        raise HTTPException(404, "Compound not found")
    return row


# --------------------------------------------------------------------------
# INSIGHTS: aggregations & rankings
# --------------------------------------------------------------------------

def _load_for_insights(
    session: Session,
    target: Optional[str] = None,
    combination_track: Optional[str] = None,
    indication_category: Optional[str] = None,
    evidence_tier: Optional[str] = None,
    perturbation_type: Optional[str] = None,
) -> List[Any]:
    """Fetch the rows an insight should be computed over.

    Every insight endpoint accepts the same optional scope filters, because
    with many DDR targets in one matrix an unscoped aggregate mixes biology
    that should not be pooled (e.g. PARP monotherapy and WEE1 + chemotherapy).

    Only the columns declared in ``insights.INSIGHT_FIELDS`` are selected. The
    insight functions read rows purely by attribute, and a SQLAlchemy Row
    exposes selected columns as attributes, so these are a drop-in substitute
    for Evidence objects. It matters at this size: building 50k ORM instances
    per request dominated the response time and, because each one joins the
    session identity map, made the garbage collector progressively slower.
    """
    columns = [getattr(Evidence, f) for f in insights_mod.INSIGHT_FIELDS]
    stmt = select(*columns)
    filters = {
        "target": target,
        "combination_track": combination_track,
        "indication_category": indication_category,
        "evidence_tier": evidence_tier,
        "perturbation_type": perturbation_type,
    }
    for field, value in filters.items():
        if value is not None:
            stmt = stmt.where(getattr(Evidence, field) == value)
    return session.exec(stmt).all()


def _scope(
    target: Optional[str] = Query(None, description="Restrict to one DDR target."),
    combination_track: Optional[str] = Query(None, description="One of the four regimen tracks."),
    indication_category: Optional[str] = Query(None),
    evidence_tier: Optional[str] = Query(None),
    perturbation_type: Optional[str] = Query(None, description="chemical | genetic."),
) -> Dict[str, Optional[str]]:
    """Shared query-parameter set scoping every /api/insights/* endpoint."""
    return {
        "target": target,
        "combination_track": combination_track,
        "indication_category": indication_category,
        "evidence_tier": evidence_tier,
        "perturbation_type": perturbation_type,
    }


def _cached(
    name: str,
    scope: Dict[str, Optional[str]],
    session: Session,
    compute,
    params_key: Any = None,
):
    """Run an insight through the cache.

    The rows are fetched lazily by the cache: on a hit nothing is queried, which
    is what keeps six simultaneous insight requests from each materialising
    their own copy of the matrix.
    """
    scope_key = tuple(sorted(scope.items()))
    return insight_cache.cached_insight(
        name,
        scope_key,
        params_key,
        loader=lambda: _load_for_insights(session, **scope),
        compute=compute,
    )


@api.get("/insights/summary", tags=["insights"])
def insight_summary(
    scope: dict = Depends(_scope), session: Session = Depends(get_session)
):
    return _cached("summary", scope, session, insights_mod.summary)


@api.get("/insights/composition", tags=["insights"])
def insight_composition(
    scope: dict = Depends(_scope), session: Session = Depends(get_session)
):
    return _cached("composition", scope, session, insights_mod.composition)


@api.get("/insights/biomarker-ranking", tags=["insights"])
def insight_biomarker_ranking(
    scope: dict = Depends(_scope), session: Session = Depends(get_session)
):
    """Biomarkers ranked over the eight scoring dimensions (see `insights.py`)."""
    return _cached("biomarker_ranking", scope, session, insights_mod.biomarker_ranking)


@api.get("/insights/indication-landscape", tags=["insights"])
def insight_indication_landscape(
    by: str = Query("compound", pattern="^(compound|target)$", description="Grid column axis."),
    scope: dict = Depends(_scope),
    session: Session = Depends(get_session),
):
    return _cached(
        "indication_landscape",
        scope,
        session,
        lambda rows: insights_mod.indication_landscape(rows, by=by),
        params_key=by,
    )


@api.get("/insights/volcano", tags=["insights"])
def insight_volcano(
    scope: dict = Depends(_scope), session: Session = Depends(get_session)
):
    return _cached("volcano", scope, session, insights_mod.volcano)


@api.get("/insights/target-overview", tags=["insights"])
def insight_target_overview(
    scope: dict = Depends(_scope), session: Session = Depends(get_session)
):
    """Per-DDR-target rollups (rows, compounds, biomarkers, top biomarkers)."""
    return _cached("target_overview", scope, session, insights_mod.target_overview)


app.include_router(api)


# --------------------------------------------------------------------------
# Public meta endpoints (no auth) — used for health checks and status.
# --------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root():
    return {
        "service": "DDR Evidence Matrix API",
        "targets": vocab.TARGETS,
        "docs": "/docs",
        "health": "ok",
        "auth_required": REQUIRE_AUTH,
        "allowed_domain": ALLOWED_EMAIL_DOMAIN if REQUIRE_AUTH else None,
    }


@app.get("/health", tags=["meta"])
@app.get("/healthz", tags=["meta"])
def healthz():
    """Liveness probe.

    Exposed at both paths on purpose. Behind Google Front End (Cloud Run),
    ``/healthz`` is reserved by the platform and answered with Google's own 404
    page - the request never reaches this process - so an external monitor must
    use ``/health``. ``/healthz`` still works locally and for in-container
    probes, and is kept so existing checks do not break.
    """
    return {"status": "ok"}
