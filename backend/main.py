"""
WEE1 Evidence Matrix API
========================

A FastAPI service implementing the "searchable evidence matrix" from the project
primer. Three capabilities:

  1. ALTER    -> POST/PATCH/DELETE /api/evidence            (create/update/remove rows)
  2. ACCESS   -> GET /api/evidence  with rich search/filter/sort/pagination
  3. INSIGHTS -> GET /api/insights/*                         (aggregations & rankings)

All /api/* routes are protected by `require_user` (Google Sign-In, @aprea.com).
Auth is enforced only when REQUIRE_AUTH=true, so local dev stays zero-config.

Storage is chosen by DATABASE_URL (SQLite locally, Cloud SQL Postgres in prod).

Interactive, auto-generated API docs: /docs (Swagger), /redoc (ReDoc).

Run locally:
    uvicorn main:app --reload
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

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

import insights as insights_mod
from auth import ALLOWED_EMAIL_DOMAIN, REQUIRE_AUTH, require_user
from database import engine, get_session, init_db
from models import Evidence, EvidenceCreate, EvidenceRead, EvidenceUpdate
from seed import generate


def _init_and_seed() -> None:
    """Create tables and seed dummy data if the table is empty."""
    init_db()
    with Session(engine) as s:
        if s.exec(select(func.count()).select_from(Evidence)).one() == 0:
            s.add_all(generate())
            s.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_and_seed()
    yield


app = FastAPI(
    title="WEE1 Evidence Matrix API",
    version="0.2.0",
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
# ACCESS: search / filter / sort / paginate
# --------------------------------------------------------------------------

SORTABLE = {
    "id", "year", "effect_size", "p_value", "q_value", "response_value",
    "n", "compound", "biomarker_name", "indication",
}


@api.get("/evidence", response_model=dict, tags=["access"])
def list_evidence(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Free-text search across compound/alias/biomarker/indication/citation."),
    compound: Optional[str] = None,
    biomarker_name: Optional[str] = None,
    biomarker_type: Optional[str] = None,
    indication: Optional[str] = None,
    model_type: Optional[str] = None,
    source_type: Optional[str] = None,
    direction: Optional[str] = None,
    treatment_setting: Optional[str] = None,
    predictive_vs_prognostic: Optional[str] = None,
    wee1_specific_vs_combo: Optional[str] = None,
    baseline_vs_pd: Optional[str] = None,
    reproducibility: Optional[str] = None,
    evidence_tier: Optional[str] = None,
    is_monotherapy: Optional[bool] = None,
    is_aprea_confidential: Optional[bool] = None,
    include_confidential: bool = Query(True, description="Set false to hide Aprea confidential rows."),
    max_p_value: Optional[float] = Query(None, description="Keep rows with p_value <= this."),
    min_year: Optional[int] = None,
    sort_by: str = Query("composite_relevance", description=f"One of {sorted(SORTABLE)} or 'composite_relevance'."),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Primary programmatic access point. Returns `{total, limit, offset, items}`."""
    stmt = select(Evidence)

    exact = {
        "compound": compound,
        "biomarker_name": biomarker_name,
        "biomarker_type": biomarker_type,
        "indication": indication,
        "model_type": model_type,
        "source_type": source_type,
        "direction": direction,
        "treatment_setting": treatment_setting,
        "predictive_vs_prognostic": predictive_vs_prognostic,
        "wee1_specific_vs_combo": wee1_specific_vs_combo,
        "baseline_vs_pd": baseline_vs_pd,
        "reproducibility": reproducibility,
        "evidence_tier": evidence_tier,
        "is_monotherapy": is_monotherapy,
        "is_aprea_confidential": is_aprea_confidential,
    }
    for field, value in exact.items():
        if value is not None:
            stmt = stmt.where(getattr(Evidence, field) == value)

    if not include_confidential:
        stmt = stmt.where(Evidence.is_aprea_confidential == False)  # noqa: E712
    if max_p_value is not None:
        stmt = stmt.where(Evidence.p_value <= max_p_value)
    if min_year is not None:
        stmt = stmt.where(Evidence.year >= min_year)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Evidence.compound.ilike(like),
                Evidence.alias.ilike(like),
                Evidence.biomarker_name.ilike(like),
                Evidence.indication.ilike(like),
                Evidence.citation.ilike(like),
                Evidence.combo_partner.ilike(like),
            )
        )

    # total (before pagination)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()

    if sort_by == "composite_relevance":
        # Surface the most statistically significant signals first (small p),
        # breaking ties by larger absolute effect. Note: effect sizes mix
        # scales (r vs Cohen's d vs hazard ratio), so p is the safer primary key.
        stmt = stmt.order_by(Evidence.p_value.asc(), func.abs(Evidence.effect_size).desc())
    elif sort_by in SORTABLE:
        col = getattr(Evidence, sort_by)
        stmt = stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())

    items = session.exec(stmt.offset(offset).limit(limit)).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@api.get("/evidence/{evidence_id}", response_model=EvidenceRead, tags=["access"])
def get_evidence(evidence_id: int, session: Session = Depends(get_session)):
    row = session.get(Evidence, evidence_id)
    if not row:
        raise HTTPException(404, "Evidence row not found")
    return row


@api.get("/vocab", tags=["access"])
def vocabularies(session: Session = Depends(get_session)):
    """Distinct values per categorical field -> powers the frontend filter dropdowns."""
    fields = [
        "compound", "biomarker_name", "biomarker_type", "indication", "model_type",
        "source_type", "direction", "treatment_setting", "predictive_vs_prognostic",
        "wee1_specific_vs_combo", "baseline_vs_pd", "reproducibility", "evidence_tier",
        "response_metric",
    ]
    out = {}
    for f in fields:
        col = getattr(Evidence, f)
        values = session.exec(select(col).distinct().where(col.is_not(None))).all()
        out[f] = sorted(v for v in values if v is not None)
    return out


# --------------------------------------------------------------------------
# ALTER: create / update / delete
# --------------------------------------------------------------------------

@api.post("/evidence", response_model=EvidenceRead, status_code=201, tags=["alter"])
def create_evidence(payload: EvidenceCreate, session: Session = Depends(get_session)):
    row = Evidence.model_validate(payload)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@api.patch("/evidence/{evidence_id}", response_model=EvidenceRead, tags=["alter"])
def update_evidence(evidence_id: int, payload: EvidenceUpdate, session: Session = Depends(get_session)):
    row = session.get(Evidence, evidence_id)
    if not row:
        raise HTTPException(404, "Evidence row not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@api.delete("/evidence/{evidence_id}", status_code=204, tags=["alter"])
def delete_evidence(evidence_id: int, session: Session = Depends(get_session)):
    row = session.get(Evidence, evidence_id)
    if not row:
        raise HTTPException(404, "Evidence row not found")
    session.delete(row)
    session.commit()


@api.post("/evidence/bulk", response_model=dict, status_code=201, tags=["alter"])
def bulk_create(payload: List[EvidenceCreate], session: Session = Depends(get_session)):
    """Insert many rows at once (e.g. output of an ingestion/ETL script)."""
    rows = [Evidence.model_validate(p) for p in payload]
    session.add_all(rows)
    session.commit()
    return {"created": len(rows)}


# --------------------------------------------------------------------------
# INSIGHTS: aggregations & rankings
# --------------------------------------------------------------------------

def _load_for_insights(session: Session, include_confidential: bool) -> List[Evidence]:
    stmt = select(Evidence)
    if not include_confidential:
        stmt = stmt.where(Evidence.is_aprea_confidential == False)  # noqa: E712
    return session.exec(stmt).all()


@api.get("/insights/summary", tags=["insights"])
def insight_summary(include_confidential: bool = True, session: Session = Depends(get_session)):
    return insights_mod.summary(_load_for_insights(session, include_confidential))


@api.get("/insights/composition", tags=["insights"])
def insight_composition(include_confidential: bool = True, session: Session = Depends(get_session)):
    return insights_mod.composition(_load_for_insights(session, include_confidential))


@api.get("/insights/biomarker-ranking", tags=["insights"])
def insight_biomarker_ranking(include_confidential: bool = True, session: Session = Depends(get_session)):
    return insights_mod.biomarker_ranking(_load_for_insights(session, include_confidential))


@api.get("/insights/indication-landscape", tags=["insights"])
def insight_indication_landscape(include_confidential: bool = True, session: Session = Depends(get_session)):
    return insights_mod.indication_landscape(_load_for_insights(session, include_confidential))


@api.get("/insights/volcano", tags=["insights"])
def insight_volcano(include_confidential: bool = True, session: Session = Depends(get_session)):
    return insights_mod.volcano(_load_for_insights(session, include_confidential))


app.include_router(api)


# --------------------------------------------------------------------------
# Public meta endpoints (no auth) — used for health checks and status.
# --------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root():
    return {
        "service": "WEE1 Evidence Matrix API",
        "docs": "/docs",
        "health": "ok",
        "auth_required": REQUIRE_AUTH,
        "allowed_domain": ALLOWED_EMAIL_DOMAIN if REQUIRE_AUTH else None,
    }


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"status": "ok"}
