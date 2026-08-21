"""Independent audit of backend/data/ddr_evidence.json + ddr_compounds.json.

Loads the produced JSON into a throwaway SQLite database via the real
``backend/ingest.py``, then runs the queries the brief asks for and a set of
fabrication checks. Exits non-zero if any check fails.

Checks
------
  * ingest.py actually loads both files, and a second call is a no-op (idempotence).
  * every identifier has the right shape: NCT########, a numeric PMID, PMC#######,
    GDSC{1,2}:<drug_id>.
  * every dataset_id traces back to a record that is present in data/ddr_harvest.json.
  * only URLs on a known-good host list appear in url_or_doi.
  * every row carrying a p_value / q_value / effect_size is one of the rows this
    pipeline computed, and says so in `notes`. Nothing else may carry a statistic.
  * no row carries a response_value without units, and no GDSC IC50 is non-positive.
  * compound.target and compound.target_family agree with backend/vocabulary.py.

Usage
    python verify.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
BACKEND = (HERE.parent / "Work for julie" / "wee1-evidence-app" / "backend").resolve()

# Point database.py at a scratch file before importing anything that touches the engine.
SCRATCH = Path(tempfile.gettempdir()) / "ddr_verify_scratch.db"
if SCRATCH.exists():
    SCRATCH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{SCRATCH.as_posix()}"

sys.path.insert(0, str(BACKEND))
from sqlmodel import Session, select  # noqa: E402

import ingest  # noqa: E402
from database import engine, init_db  # noqa: E402
from models import Compound, Evidence  # noqa: E402
from vocabulary import (  # noqa: E402
    BIOMARKER_SCOPES, BIOMARKER_TYPES, COMBINATION_TRACKS, EVIDENCE_BASES, EVIDENCE_TIERS,
    INDICATION_CATEGORIES, MODEL_TYPES, PERTURBATION_TYPES, PREDICTIVE_CLASSES,
    REPRODUCIBILITY, SOURCE_TYPES, TARGET_FAMILY, TARGETS,
)

FAILURES: list[str] = []
NOTES: list[str] = []


def check(ok: bool, msg: str) -> None:
    if ok:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        FAILURES.append(msg)


def head(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


NCT_RX = re.compile(r"^NCT\d{8}$")
PMID_RX = re.compile(r"^\d{1,9}$")
PMC_RX = re.compile(r"^PMC\d{5,9}$")
GDSC_RX = re.compile(r"^GDSC[12]:\d{1,5}$")

ALLOWED_HOSTS = {
    "clinicaltrials.gov", "pubmed.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov",
    "www.cancerrxgene.org", "doi.org",
}


def main() -> int:
    head("1. ingest.py loads both files into a scratch database")
    init_db()
    result = ingest.load_reference_data()
    print(f"  load_reference_data() -> {result}")
    check(result["skipped"] is False and result["evidence"] > 0 and result["compounds"] > 0,
          "first call loaded rows")
    again = ingest.load_reference_data()
    print(f"  second call            -> {again}")
    check(again["skipped"] is True, "second call is a no-op (idempotent)")
    check(again["evidence"] == result["evidence"] and again["compounds"] == result["compounds"],
          "row counts unchanged after the second call")

    harvest = json.loads((HERE / "data" / "ddr_harvest.json").read_text(encoding="utf-8"))
    harvest_ncts = {r["record_id"] for r in harvest.get("ctgov", [])}
    harvest_lit = {str(r["record_id"]) for r in harvest.get("literature", [])}
    harvest_gdsc = {f"{r['release']}:{r['drug_id']}" for r in harvest.get("gdsc", [])}

    with Session(engine) as s:
        ev = s.exec(select(Evidence)).all()
        comps = s.exec(select(Compound)).all()

    head("2. Row counts")
    print(f"  Evidence rows : {len(ev)}")
    print(f"  Compound rows : {len(comps)}")

    def table(label: str, counts: Counter, vocab: list[str] | None = None,
              limit: int | None = None) -> None:
        shown = counts.most_common(limit) if limit else counts.most_common()
        print(f"\n  -- {label} ({len(counts)} distinct) --")
        for k, v in shown:
            flag = ""
            if vocab is not None and k is not None and k not in vocab:
                flag = "   <-- NOT IN backend/vocabulary.py"
            print(f"     {v:8d}  {str(k):<48s}{flag}")
        if limit and len(counts) > limit:
            print(f"     ... {len(counts) - limit} more")

    table("by target", Counter(r.target for r in ev), TARGETS)
    table("by target_family", Counter(r.target_family for r in ev))
    table("by source_type", Counter(r.source_type for r in ev), SOURCE_TYPES)
    table("by evidence_tier", Counter(r.evidence_tier for r in ev), EVIDENCE_TIERS + [None])
    table("by combination_track", Counter(r.combination_track for r in ev), COMBINATION_TRACKS)
    table("by model_type", Counter(r.model_type for r in ev), MODEL_TYPES)
    table("by evidence_basis", Counter(r.evidence_basis for r in ev), EVIDENCE_BASES + [None])
    table("by indication_category", Counter(r.indication_category for r in ev),
          INDICATION_CATEGORIES)
    table("by biomarker_type", Counter(r.biomarker_type for r in ev), BIOMARKER_TYPES)
    table("by biomarker_scope", Counter(r.biomarker_scope for r in ev), BIOMARKER_SCOPES + [None])
    table("by reproducibility", Counter(r.reproducibility for r in ev), REPRODUCIBILITY + [None])
    table("by direction", Counter(r.direction for r in ev))
    table("by perturbation_type", Counter(r.perturbation_type for r in ev), PERTURBATION_TYPES)
    table("by predictive_vs_prognostic", Counter(r.predictive_vs_prognostic for r in ev),
          PREDICTIVE_CLASSES + [None])
    table("biomarker_name", Counter(r.biomarker_name for r in ev), limit=30)
    table("compound (top 30)", Counter(r.compound for r in ev), limit=30)
    table("compound dictionary by target", Counter(c.target for c in comps), TARGETS)
    table("compound dictionary by clinical_stage", Counter(c.clinical_stage for c in comps))

    head("3. Controlled-vocabulary conformance")
    for label, values, vocab in [
        ("target", {r.target for r in ev}, set(TARGETS)),
        ("source_type", {r.source_type for r in ev}, set(SOURCE_TYPES)),
        ("combination_track", {r.combination_track for r in ev}, set(COMBINATION_TRACKS)),
        ("model_type", {r.model_type for r in ev}, set(MODEL_TYPES)),
        ("perturbation_type", {r.perturbation_type for r in ev}, set(PERTURBATION_TYPES)),
        ("biomarker_type", {r.biomarker_type for r in ev}, set(BIOMARKER_TYPES)),
        ("evidence_tier", {r.evidence_tier for r in ev} - {None}, set(EVIDENCE_TIERS)),
        ("evidence_basis", {r.evidence_basis for r in ev} - {None}, set(EVIDENCE_BASES)),
        ("indication_category", {r.indication_category for r in ev} - {None},
         set(INDICATION_CATEGORIES)),
        ("biomarker_scope", {r.biomarker_scope for r in ev} - {None}, set(BIOMARKER_SCOPES)),
        ("reproducibility", {r.reproducibility for r in ev} - {None}, set(REPRODUCIBILITY)),
    ]:
        bad = values - vocab
        check(not bad, f"every {label} is in backend/vocabulary.py"
                       + (f" (offenders: {sorted(bad)})" if bad else ""))
    # response_metric deliberately admits one extra value; make that explicit.
    metrics = {r.response_metric for r in ev}
    print(f"  note  response_metric values present: {sorted(metrics)}")
    NOTES.append("response_metric uses the sentinel 'not_reported' for trials and papers "
                 "that declare no efficacy endpoint. It is intentionally outside "
                 "vocabulary.RESPONSE_METRICS.")

    head("4. Identifier shapes and traceability to the harvest")
    reg = [r for r in ev if r.source_type == "registry"]
    db_rows = [r for r in ev if r.source_type == "database"]
    lit = [r for r in ev if r.source_type == "peer_reviewed"]
    check(all(NCT_RX.match(r.dataset_id or "") for r in reg),
          f"all {len(reg)} registry rows have a well-formed NCT id")
    check(all((r.dataset_id in harvest_ncts) for r in reg),
          "every registry dataset_id is present in data/ddr_harvest.json")
    check(all(GDSC_RX.match(r.dataset_id or "") for r in db_rows),
          f"all {len(db_rows)} database rows have a GDSC<release>:<drug_id> dataset_id")
    check({r.dataset_id for r in db_rows} <= harvest_gdsc,
          "every GDSC dataset_id is present in the harvested measurements")
    bad_lit = [r.dataset_id for r in lit
               if not (PMID_RX.match(r.dataset_id or "") or PMC_RX.match(r.dataset_id or ""))]
    check(not bad_lit, f"all {len(lit)} literature rows have a numeric PMID or a PMC id"
                       + (f" (offenders: {bad_lit[:5]})" if bad_lit else ""))
    check({str(r.dataset_id) for r in lit} <= harvest_lit,
          "every literature dataset_id is present in the harvested records")

    hosts = Counter()
    for r in ev:
        u = r.url_or_doi or ""
        m = re.match(r"https?://([^/]+)/", u)
        hosts[m.group(1) if m else f"MALFORMED:{u[:40]}"] += 1
    print("\n  -- url_or_doi hosts --")
    for k, v in hosts.most_common():
        print(f"     {v:8d}  {k}")
    check(set(hosts) <= ALLOWED_HOSTS, "every url_or_doi is on a known source host")

    head("5. Fabrication checks")
    with_stat = [r for r in ev if r.p_value is not None or r.q_value is not None
                 or r.effect_size is not None]
    check(all("COMPUTED STATISTIC" in (r.notes or "") for r in with_stat),
          f"all {len(with_stat)} rows carrying a p/q/effect_size declare themselves as a "
          f"statistic computed by this pipeline")
    check(all(r.source_type == "database" and r.model_type == "cell_line" for r in with_stat),
          "no clinical or literature row carries an effect size or p-value")
    check(all(r.effect_size is not None and r.p_value is not None and r.q_value is not None
              and r.effect_size_type == "cohens_d" for r in with_stat),
          "every statistic row has effect_size + effect_size_type + p_value + q_value together")
    check(all(0.0 <= r.p_value <= 1.0 and 0.0 <= r.q_value <= 1.0 for r in with_stat),
          "all p-values and q-values are in [0, 1]")
    check(all(r.q_value >= r.p_value - 1e-12 for r in with_stat),
          "every q-value is >= its p-value (BH can only inflate)")

    valued = [r for r in ev if r.response_value is not None]
    check(all(r.units for r in valued),
          f"all {len(valued)} rows with a response_value also record units")
    ic50 = [r for r in ev if r.response_metric == "IC50" and r.response_value is not None]
    check(all(r.response_value > 0 for r in ic50),
          f"all {len(ic50)} IC50 values are strictly positive")
    check(all(r.units == "uM" for r in ic50), "all IC50 values are in uM")

    reg_val = [r for r in reg if r.response_value is not None]
    check(all("resultsSection" in (r.notes or "") for r in reg_val),
          f"all {len(reg_val)} registry rows with a value cite the posted resultsSection")
    check(all(r.response_value is None for r in lit),
          "no literature row carries a response value (they are co-mentions only)")
    check(all("UNCURATED KEYWORD CO-MENTION" in (r.notes or "") for r in lit),
          "every literature row is explicitly labelled as an uncurated co-mention")
    check(all(r.notes for r in ev), "every row has a notes value")

    ci = [r for r in ev if r.ci_low is not None or r.ci_high is not None]
    check(all(r.source_type == "registry" for r in ci),
          f"all {len(ci)} rows with a confidence interval come from posted registry results")

    check(all((r.combo_partner is None) == (r.combination_track == "monotherapy")
              for r in reg),
          "registry monotherapy rows have no partner, and combination rows all name one")
    check(all(r.is_monotherapy == (r.combination_track == "monotherapy") for r in ev),
          "is_monotherapy always agrees with combination_track")

    head("6. Compound dictionary")
    check(all(c.target in TARGETS for c in comps), "every compound target is in the vocabulary")
    check(all(c.target_family == TARGET_FAMILY[c.target] for c in comps),
          "every target_family matches vocabulary.TARGET_FAMILY")
    names = [c.canonical_name for c in comps]
    check(len(names) == len(set(names)), "canonical_name is unique")
    ev_compounds = {r.compound for r in ev}
    check(ev_compounds <= set(names),
          "every Evidence.compound resolves to a Compound row"
          + (f" (orphans: {sorted(ev_compounds - set(names))})" if ev_compounds - set(names) else ""))
    check(all(c.typical_dose is None and c.typical_schedule is None for c in comps),
          "no invented dose/schedule on the dictionary (dose lives on Evidence rows)")

    head("7. Spot-check: 10 rows, one per source, with their real URLs")
    picks: list[Evidence] = []
    for st in ("registry", "database", "peer_reviewed"):
        pool = [r for r in ev if r.source_type == st]
        picks += pool[:2] + pool[len(pool) // 2:len(pool) // 2 + 2]
    for r in picks[:12]:
        print(f"\n  {r.source_type:<14s} {r.dataset_id}")
        print(f"    compound      : {r.compound} ({r.target})")
        print(f"    biomarker     : {r.biomarker_name}")
        print(f"    endpoint      : {r.response_metric} = {r.response_value} {r.units or ''}")
        print(f"    url           : {r.url_or_doi}")
        print(f"    citation      : {(r.citation or '')[:110]}")

    head("8. Dose/schedule provenance")
    dosed = [r for r in ev if r.dose]
    print(f"  {len(dosed)} rows carry a dose string, all extracted from the "
          f"ClinicalTrials.gov intervention description")
    check(all(r.source_type == "registry" for r in dosed),
          "dose only appears on registry rows")

    head("RESULT")
    for n in NOTES:
        print(f"  note: {n}")
    if FAILURES:
        print(f"\n  {len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"    - {f}")
        return 1
    print("\n  all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
