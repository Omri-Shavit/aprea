"""Harvest real DDR-inhibitor evidence from ClinicalTrials.gov, GDSC and PubMed/PMC.

Nothing in this file invents a value. Every field written to
``data/ddr_harvest.json`` is either copied from an API response / local dataset file,
or is a label derived by a documented rule from such a value.

Layers, in the priority order of the program brief
-------------------------------------------------
  (a) ClinicalTrials.gov API v2   - every trial naming a compound in ddr_config, with
                                    interventions, enrolment, conditions, outcome
                                    measures and (where posted) real reported results.
  (b) GDSC release 8.5            - per-cell-line LN_IC50 / AUC / Z_SCORE for the 31 DDR
                                    compounds present in gdsc_screened_compounds.csv,
                                    read from the xlsx files already in
                                    ../wee1_scavenger/cache/, joined to GDSC cell-line
                                    annotations and to Cell Model Passports driver
                                    mutation calls.
  (c) PubMed / PMC                - E-utilities, reusing the WEE1 corpus already in
                                    ../wee1_scavenger/data/harvest.json and fetching
                                    only the non-WEE1 DDR compounds.

Raw API responses are cached under ``cache/`` so re-runs are cheap.

Usage
    python harvest_ddr.py                # all layers
    python harvest_ddr.py ctgov gdsc     # named layers only
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import requests

import ddr_config as cfg

HERE = Path(__file__).parent
CACHE = HERE / "cache"
DATA = HERE / "data"
CACHE.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

WEE1_DIR = HERE.parent / "wee1_scavenger"
WEE1_CACHE = WEE1_DIR / "cache"
WEE1_DATA = WEE1_DIR / "data"

HEADERS = {"User-Agent": cfg.USER_AGENT}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_SLEEP = 0.40
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

CMP_MUTATIONS_URL = "https://cog.sanger.ac.uk/cmp/download/mutations_summary_20230202.zip"
CMP_MODEL_LIST_URL = "https://cog.sanger.ac.uk/cmp/download/model_list_20230923.csv"


def log(msg: str) -> None:
    print(msg, flush=True)


# ===========================================================================
# HTTP with on-disk cache + retry (same contract as wee1_scavenger/harvest.py)
# ===========================================================================
def cached_get(url: str, params: dict | None, cache_name: str, method: str = "GET",
               json_body: dict | None = None, timeout: int = 120, force: bool = False,
               data: dict | None = None, attempts: int = 5, validate=None) -> str:
    path = CACHE / cache_name
    if path.exists() and not force:
        cached = path.read_text(encoding="utf-8")
        if validate is None or validate(cached):
            return cached
        log(f"        cached {cache_name} failed validation; refetching")
    last = None
    for attempt in range(attempts):
        try:
            if method == "GET":
                r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
            elif data is not None:
                r = requests.post(url, params=params, data=data, headers=HEADERS, timeout=timeout)
            else:
                r = requests.post(url, params=params, json=json_body, headers=HEADERS,
                                  timeout=timeout)
            r.raise_for_status()
            text = r.text
            if validate is not None and not validate(text):
                raise ValueError("response failed validation")
            path.write_text(text, encoding="utf-8")
            return text
        except Exception as e:  # noqa: BLE001
            last = e
            wait = 2 ** attempt + 1
            log(f"        retry {attempt + 1}/{attempts} after {type(e).__name__} (sleep {wait}s)")
            time.sleep(wait)
    raise RuntimeError(f"all {attempts} attempts failed for {cache_name}: {last}")


def download(url: str, name: str, attempts: int = 4) -> Path:
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        return path
    tmp = path.with_suffix(path.suffix + ".part")
    for attempt in range(attempts):
        log(f"      downloading {name} (attempt {attempt + 1}) ...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=900, stream=True)
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            tmp.replace(path)
            return path
        except Exception as e:  # noqa: BLE001
            log(f"        {type(e).__name__}: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"could not download {name}")


def load_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(CONTROL_CHARS.sub(" ", text))


def no_ncbi_error(text: str) -> bool:
    return "<ERROR>" not in text and "NCBI C++ Exception" not in text


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:60]


# ===========================================================================
# (a) ClinicalTrials.gov API v2
# ===========================================================================
PHASE_LABEL = {"EARLY_PHASE1": "Early Phase 1", "PHASE1": "Phase 1", "PHASE2": "Phase 2",
               "PHASE3": "Phase 3", "PHASE4": "Phase 4", "NA": "N/A"}
PHASE_RANK = {"EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4}

# Cap on how many posted outcome measures are turned into value-carrying rows per trial,
# so a single heavily-reported study cannot dominate the table. Measures are ranked
# PRIMARY first, then by cfg.METRIC_RANK.
MAX_PARSED_OUTCOMES_PER_TRIAL = 3

map_outcome_metric = cfg.map_outcome_metric


def _num(value) -> float | None:
    """Parse a registry measurement value. Returns None for 'NA', '', ranges, etc."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() in ("NA", "N/A", "NAN", "NR", "-"):
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_posted_results(results_section: dict) -> list[dict]:
    """Extract real reported efficacy values from a v2 resultsSection.

    Conservative on purpose: a measure is only used when its title maps unambiguously
    onto the controlled metric vocabulary, it has exactly one class and one category
    (i.e. it is not split into sub-measures that would need interpretation), and the
    measurement parses as a number. Everything else is dropped rather than guessed.
    """
    out: list[dict] = []
    measures = ((results_section or {}).get("outcomeMeasuresModule") or {}).get(
        "outcomeMeasures") or []
    candidates = []
    for om in measures:
        metric = map_outcome_metric(om.get("title", ""))
        if not metric:
            continue
        classes = om.get("classes") or []
        if len(classes) != 1:
            continue
        cats = classes[0].get("categories") or []
        if len(cats) != 1:
            continue
        group_titles = {g.get("id"): g.get("title", "") for g in (om.get("groups") or [])}
        denoms: dict[str, int | None] = {}
        for d in (om.get("denoms") or []):
            for c in (d.get("counts") or []):
                v = _num(c.get("value"))
                denoms[c.get("groupId")] = int(v) if v is not None else None
        rows = []
        for meas in (cats[0].get("measurements") or []):
            val = _num(meas.get("value"))
            if val is None:
                continue
            gid = meas.get("groupId")
            rows.append({
                "metric": metric,
                "param_type": om.get("paramType", ""),
                "units": om.get("unitOfMeasure", ""),
                "measure_title": om.get("title", ""),
                "measure_type": om.get("type", ""),
                "time_frame": om.get("timeFrame", ""),
                "group_title": group_titles.get(gid, gid or ""),
                "group_n": denoms.get(gid),
                "value": val,
                "ci_low": _num(meas.get("lowerLimit")),
                "ci_high": _num(meas.get("upperLimit")),
                "population_description": om.get("populationDescription", ""),
            })
        if rows:
            candidates.append((0 if om.get("type") == "PRIMARY" else 1,
                               cfg.METRIC_RANK.get(metric, 9), rows))
    candidates.sort(key=lambda t: (t[0], t[1]))
    for _, _, rows in candidates[:MAX_PARSED_OUTCOMES_PER_TRIAL]:
        out.extend(rows)
    return out


DOSE_RX = re.compile(
    r"\b(\d+(?:\.\d+)?)\s?(mg/m2|mg/m\^2|mg/kg|mg|g/m2|mcg)\b\s*"
    r"(?:(BID|QD|TID|QID|once daily|twice daily|daily|weekly)\b)?", re.I)
SCHEDULE_RX = re.compile(
    r"\b(days? \d+(?:\s?[-–]\s?\d+)?(?:,\s?\d+(?:\s?[-–]\s?\d+)?)*(?: of (?:a |each )?"
    r"\d+[\-\s]day cycle)?|\d+ days? on\s?/?\s?\d+ days? off|"
    r"(?:once|twice) (?:daily|weekly)|q\d+[dwh]|every \d+ (?:days?|weeks?)|"
    r"BID|QD|TID|continuous(?:ly)?)\b", re.I)


def extract_dose(text: str) -> str | None:
    m = DOSE_RX.search(text or "")
    if not m:
        return None
    dose = f"{m.group(1)} {m.group(2).lower()}"
    if m.group(3):
        dose += f" {m.group(3).upper() if len(m.group(3)) <= 3 else m.group(3).lower()}"
    return dose


def extract_schedule(text: str) -> str | None:
    m = SCHEDULE_RX.search(text or "")
    return m.group(0) if m else None


SPECIMEN_PATTERNS = [
    (re.compile(r"\b(circulating tumou?r DNA|ctDNA|cell[\-\s]free DNA|cfDNA|liquid biopsy)\b",
                re.I), "plasma_ctdna"),
    (re.compile(r"\b(tumou?r (?:tissue|biopsy|sample|specimen)|archival tissue|"
                r"formalin[\-\s]fixed|\bFFPE\b|paired biops|core biops)\b", re.I), "tumor_tissue"),
    (re.compile(r"\bskin biops\w*\b", re.I), "skin_biopsy"),
    (re.compile(r"\b(peripheral blood mononuclear|\bPBMC\b)\b", re.I), "pbmc"),
    (re.compile(r"\b(whole blood|blood sample)\b", re.I), "whole_blood"),
]


def detect_specimen(text: str) -> str | None:
    for rx, label in SPECIMEN_PATTERNS:
        if rx.search(text or ""):
            return label
    return None


PAIRED_RX = re.compile(r"\b(paired|pre[\-\s]and[\-\s]post|on[\-\s]treatment|during treatment|"
                       r"post[\-\s]dose|serial (?:biops|sampl))\b", re.I)
BASELINE_RX = re.compile(r"\b(baseline|pre[\-\s]treatment|archival|at screening|prior to "
                         r"(?:treatment|study drug))\b", re.I)


def detect_specimen_timing(text: str) -> str:
    if PAIRED_RX.search(text or ""):
        return "on_treatment"
    if BASELINE_RX.search(text or ""):
        return "baseline"
    return "not_reported"


def harvest_clinicaltrials() -> list[dict]:
    log("\n[a] ClinicalTrials.gov API v2 ...")
    terms = cfg.ctgov_search_terms()
    log(f"      {len(terms)} search terms")
    studies: dict[str, dict] = {}
    for i, term in enumerate(terms):
        token, page = None, 0
        while True:
            params = {"query.term": f'"{term}"', "pageSize": 100}
            if token:
                params["pageToken"] = token
            key = f"ctgov_{slug(term)}_{page}.json"
            try:
                body = load_json(cached_get("https://clinicaltrials.gov/api/v2/studies",
                                            params, key))
            except RuntimeError as e:
                log(f"      !! term {term!r} page {page} failed permanently: {e}")
                break
            for s in body.get("studies", []):
                nct = s["protocolSection"]["identificationModule"]["nctId"]
                studies[nct] = s
            token = body.get("nextPageToken")
            page += 1
            if not token:
                break
        if (i + 1) % 25 == 0:
            log(f"      ... {i + 1}/{len(terms)} terms, {len(studies)} unique NCT ids so far")
    log(f"      {len(studies)} unique NCT records retrieved")

    records: list[dict] = []
    kept = 0
    for nct, s in sorted(studies.items()):
        ps = s.get("protocolSection", {})
        ident = ps.get("identificationModule", {}) or {}
        design = ps.get("designModule", {}) or {}
        status_mod = ps.get("statusModule", {}) or {}
        cond_mod = ps.get("conditionsModule", {}) or {}
        arms_mod = ps.get("armsInterventionsModule", {}) or {}
        elig = (ps.get("eligibilityModule", {}) or {}).get("eligibilityCriteria", "") or ""
        desc_mod = ps.get("descriptionModule", {}) or {}
        sponsor_mod = ps.get("sponsorCollaboratorsModule", {}) or {}
        outcomes = ps.get("outcomesModule", {}) or {}

        title = ident.get("briefTitle", "") or ident.get("officialTitle", "")
        official = ident.get("officialTitle", "") or ""
        brief_summary = desc_mod.get("briefSummary", "") or ""
        interventions = arms_mod.get("interventions", []) or []
        arm_groups = arms_mod.get("armGroups") or []

        iv_blob = " ; ".join(
            (iv.get("name", "") + " " + " ".join(iv.get("otherNames") or []))
            for iv in interventions)
        arm_blob = " ; ".join((a.get("label", "") + " " + (a.get("description") or ""))
                              for a in arm_groups)

        # A DDR agent must actually be an intervention, or be named in the title / arms.
        # Eligibility text is deliberately NOT used for drug detection: it names prior
        # therapies and exclusion drugs the trial is not testing.
        drugs = cfg.find_compounds(iv_blob, title, official, arm_blob)
        if not drugs:
            continue
        kept += 1

        drug_rx = [cfg.ALIAS_REGEX[d] for d in drugs]
        partners: list[str] = []
        partner_types: list[str] = []
        for iv in interventions:
            nm = re.sub(r"\s+", " ", iv.get("name", "") or "").strip()
            if not nm:
                continue
            itype = iv.get("type")
            if itype not in ("DRUG", "BIOLOGICAL", "RADIATION", "PROCEDURE",
                             "COMBINATION_PRODUCT", "DIETARY_SUPPLEMENT", None):
                continue
            names_blob = nm + " " + " ".join(iv.get("otherNames") or [])
            if any(rx.search(names_blob) for rx in drug_rx):
                continue
            if cfg.mentions_generic_ddri(names_blob):
                continue
            if nm.lower() not in [p.lower() for p in partners]:
                partners.append(nm)
                partner_types.append(itype or "")

        phases_raw = design.get("phases") or []
        enroll_info = design.get("enrollmentInfo") or {}
        primary_outcomes = [o.get("measure", "") for o in (outcomes.get("primaryOutcomes") or [])]
        secondary_outcomes = [o.get("measure", "")
                              for o in (outcomes.get("secondaryOutcomes") or [])]
        outcome_desc = " ; ".join(
            (o.get("measure", "") + " " + (o.get("description") or ""))
            for o in ((outcomes.get("primaryOutcomes") or [])
                      + (outcomes.get("secondaryOutcomes") or [])))

        design_info = design.get("designInfo") or {}
        allocation = design_info.get("allocation", "") or ""

        # Per-DDR-drug dose/schedule from the intervention description, when stated.
        dose_by_drug: dict[str, dict[str, str | None]] = {}
        for iv in interventions:
            names_blob = (iv.get("name", "") or "") + " " + " ".join(iv.get("otherNames") or [])
            desc = iv.get("description", "") or ""
            for d in drugs:
                if cfg.ALIAS_REGEX[d].search(names_blob):
                    dose_by_drug.setdefault(d, {
                        "dose": extract_dose(desc) or extract_dose(names_blob),
                        "schedule": extract_schedule(desc),
                    })

        design_blob = " ".join([title, official, arm_blob, " ; ".join(primary_outcomes),
                                " ; ".join(cond_mod.get("conditions", []) or [])])
        records.append({
            "layer": "ctgov",
            "record_id": nct,
            "url": f"https://clinicaltrials.gov/study/{nct}",
            "results_url": (f"https://clinicaltrials.gov/study/{nct}?tab=results"
                            if s.get("hasResults") else None),
            "drugs": drugs,
            "drug_name_as_written": iv_blob[:600] or None,
            "dose_by_drug": dose_by_drug,
            "title": title,
            "official_title": official or None,
            "phases_raw": phases_raw,
            "phase_label": ", ".join(PHASE_LABEL.get(p, p.title()) for p in phases_raw) or "N/A",
            "max_phase_rank": max([PHASE_RANK[p] for p in phases_raw if p in PHASE_RANK],
                                  default=None),
            "status": (status_mod.get("overallStatus", "") or "").replace("_", " ").title() or None,
            "study_type": design.get("studyType") or None,
            "allocation": allocation or None,
            "conditions": cond_mod.get("conditions", []) or [],
            "partners": partners,
            "partner_types": partner_types,
            "enrollment": enroll_info.get("count"),
            "enrollment_type": enroll_info.get("type"),
            "start_date": (status_mod.get("startDateStruct", {}) or {}).get("date") or None,
            "sponsor": ((sponsor_mod.get("leadSponsor") or {}).get("name") or None),
            "primary_outcomes": primary_outcomes,
            "secondary_outcomes": secondary_outcomes,
            "has_results": bool(s.get("hasResults")),
            "posted_results": (parse_posted_results(s.get("resultsSection") or {})
                               if s.get("hasResults") else []),
            # Biomarker detection is split by where the term was found: design fields are
            # what the trial was built around; eligibility text is weaker evidence.
            "biomarkers_design": cfg.find_biomarkers(design_blob),
            "biomarkers_eligibility": cfg.find_biomarkers(elig),
            "biomarkers_outcomes": cfg.find_biomarkers(outcome_desc),
            "treatment_setting": cfg.treatment_setting_for(title, official, elig),
            "specimen_type": detect_specimen(elig + " " + outcome_desc),
            "specimen_timing": detect_specimen_timing(outcome_desc + " " + elig),
            "brief_summary": brief_summary[:4000] or None,
        })
    log(f"      {kept} studies confirmed to test a DDR agent in the dictionary")
    n_res = sum(1 for r in records if r["posted_results"])
    log(f"      {n_res} of them have posted results that parsed into numeric efficacy values")
    return records


# ===========================================================================
# (b) GDSC release 8.5 - real per-cell-line dose response
# ===========================================================================
def _load_cmp_mutations() -> tuple[dict[str, set[str]], set[str]]:
    """Cell Model Passports driver mutations, keyed by Sanger model id.

    Returns ``(model_id -> {mutated gene symbols}, set of sequenced model ids)``.
    The sequenced set is the denominator for calling a model wild-type: a model that
    was never sequenced must be reported as uncharacterised, not as wild-type.
    """
    zpath = download(CMP_MUTATIONS_URL, "cmp_mutations_summary.zip")
    with zipfile.ZipFile(zpath) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        mut = pd.read_csv(z.open(name), low_memory=False)
    by_model: dict[str, set[str]] = {}
    for model_id, gene in zip(mut["model_id"], mut["gene_symbol"]):
        if isinstance(model_id, str) and isinstance(gene, str):
            by_model.setdefault(model_id, set()).add(gene)

    mpath = download(CMP_MODEL_LIST_URL, "cmp_model_list.csv")
    models = pd.read_csv(mpath, low_memory=False)
    sequenced = set(by_model)
    if "mutational_burden" in models.columns:
        sequenced |= set(models.loc[models["mutational_burden"].notna(), "model_id"]
                         .dropna().astype(str))
    log(f"      Cell Model Passports: {len(by_model)} models with driver mutation calls, "
        f"{len(sequenced)} models with exome sequencing")
    return by_model, sequenced


def harvest_gdsc() -> tuple[list[dict], list[dict]]:
    """Return (per-measurement records, per-compound summary records)."""
    log("\n[b] GDSC release 8.5 (local cache) ...")
    comp_path = WEE1_CACHE / "gdsc_screened_compounds.csv"
    if not comp_path.exists():
        raise FileNotFoundError(f"missing {comp_path} - run the WEE1 harvester first")
    comps = pd.read_csv(comp_path)

    # Re-derive the DDR compound set from the CSV rather than trusting the hard-coded map,
    # then assert the two agree.
    ddr_rx = (r"WEE1|\bATR\b|\bATM\b|CHEK1|CHEK2|PRKDC|DNAPK|DNA-PK|PARP|POLQ|USP1|"
              r"DYRK|RAD51|PKMYT1|MYT1|Tankyrase")
    target_blob = comps["TARGET"].fillna("")
    derived = set(comps.loc[target_blob.str.contains(ddr_rx, case=False, regex=True), "DRUG_ID"])
    mapped = set(cfg.GDSC_DRUG_ID_TO_CANONICAL)
    log(f"      {len(derived)} GDSC compounds carry a DDR target annotation; "
        f"{len(mapped)} are mapped to a dictionary compound")
    unmapped = sorted(derived - mapped)
    if unmapped:
        names = comps.set_index("DRUG_ID").loc[unmapped, ["DRUG_NAME", "TARGET"]]
        log("      DDR-annotated but intentionally unmapped (target outside the schema "
            "vocabulary, see ddr_config.NOT_DDR_AGENTS):")
        for did, row in names.iterrows():
            log(f"        {did:5d}  {row['DRUG_NAME']:<26s} {row['TARGET']}")
    for did, expected in cfg.GDSC_DRUG_ID_EXPECTED_NAME.items():
        actual = comps.loc[comps["DRUG_ID"] == did, "DRUG_NAME"]
        if actual.empty:
            raise AssertionError(f"GDSC drug id {did} not found in {comp_path.name}")
        if str(actual.iloc[0]).strip() != expected:
            raise AssertionError(
                f"GDSC drug id {did}: expected DRUG_NAME {expected!r}, got {actual.iloc[0]!r}")
    log("      drug-id -> compound map verified against the CSV")

    target_by_id = dict(zip(comps["DRUG_ID"], comps["TARGET"].fillna("")))
    pathway_by_id = dict(zip(comps["DRUG_ID"], comps["TARGET_PATHWAY"].fillna("")))

    # Cell-line annotations: TCGA label and tissue from the GDSC annotation workbook.
    cells = pd.read_excel(WEE1_CACHE / "gdsc_cell_lines.xlsx", sheet_name=0)
    cells.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in cells.columns]
    cosmic_col = next(c for c in cells.columns if "COSMIC" in c.upper())
    tissue_col = next(c for c in cells.columns if c.startswith("GDSC Tissue descriptor 1"))
    tissue2_col = next(c for c in cells.columns if c.startswith("GDSC Tissue descriptor 2"))
    tcga_col = next(c for c in cells.columns if "matching TCGA" in c)
    msi_col = next((c for c in cells.columns if "instability" in c), None)
    cell_meta: dict[int, dict] = {}
    for _, row in cells.iterrows():
        try:
            key = int(row[cosmic_col])
        except (TypeError, ValueError):
            continue
        cell_meta[key] = {
            "tissue": None if pd.isna(row[tissue_col]) else str(row[tissue_col]),
            "tissue_detail": None if pd.isna(row[tissue2_col]) else str(row[tissue2_col]),
            "tcga_label": None if pd.isna(row[tcga_col]) else str(row[tcga_col]),
            "msi": None if (msi_col is None or pd.isna(row[msi_col])) else str(row[msi_col]),
        }
    log(f"      {len(cell_meta)} GDSC cell-line annotations loaded")

    mut_by_model, sequenced_models = _load_cmp_mutations()

    measurements: list[dict] = []
    summaries: list[dict] = []
    for release, fname in [("GDSC1", "gdsc_GDSC1_fitted.xlsx"),
                           ("GDSC2", "gdsc_GDSC2_fitted.xlsx")]:
        path = WEE1_CACHE / fname
        if not path.exists():
            log(f"      !! {path} missing - skipping {release}")
            continue
        log(f"      parsing {release} ({path.stat().st_size / 1e6:.0f} MB) ...")
        df = pd.read_excel(path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        sub = df[df["DRUG_ID"].isin(mapped)].copy()
        log(f"        {len(sub)} rows for DDR compounds "
            f"({sub['DRUG_ID'].nunique()} compounds, {sub['CELL_LINE_NAME'].nunique()} lines)")
        for drug_id, g in sub.groupby("DRUG_ID"):
            canon = cfg.GDSC_DRUG_ID_TO_CANONICAL[int(drug_id)]
            drug_name = str(g["DRUG_NAME"].iloc[0])
            url = ("https://www.cancerrxgene.org/compound/"
                   f"{drug_name.replace(' ', '%20')}/{int(drug_id)}/overview")
            summaries.append({
                "layer": "gdsc_summary",
                "release": release,
                "drug_id": int(drug_id),
                "drug_name": drug_name,
                "canonical": canon,
                "gdsc_target": target_by_id.get(drug_id) or None,
                "gdsc_pathway": pathway_by_id.get(drug_id) or None,
                "n_measurements": int(len(g)),
                "n_cell_lines": int(g["CELL_LINE_NAME"].nunique()),
                "median_ln_ic50": float(g["LN_IC50"].median()),
                "median_auc": float(g["AUC"].median()),
                "url": url,
            })
            for _, row in g.iterrows():
                cosmic = row.get("COSMIC_ID")
                try:
                    cosmic_i = int(cosmic)
                except (TypeError, ValueError):
                    cosmic_i = None
                meta = cell_meta.get(cosmic_i, {}) if cosmic_i is not None else {}
                model_id = row.get("SANGER_MODEL_ID")
                model_id = str(model_id) if isinstance(model_id, str) else None
                ln = row.get("LN_IC50")
                measurements.append({
                    "layer": "gdsc",
                    "release": release,
                    "drug_id": int(drug_id),
                    "drug_name": drug_name,
                    "canonical": canon,
                    "gdsc_target": target_by_id.get(drug_id) or None,
                    "cell_line": (None if pd.isna(row.get("CELL_LINE_NAME"))
                                  else str(row["CELL_LINE_NAME"])),
                    "cosmic_id": cosmic_i,
                    "sanger_model_id": model_id,
                    "tcga_desc": (None if pd.isna(row.get("TCGA_DESC"))
                                  else str(row["TCGA_DESC"])),
                    "tissue": meta.get("tissue"),
                    "tissue_detail": meta.get("tissue_detail"),
                    "tcga_label": meta.get("tcga_label"),
                    "msi": meta.get("msi"),
                    # GDSC publishes LN_IC50 = natural log of the fitted IC50 in micromolar.
                    "ln_ic50": None if pd.isna(ln) else float(ln),
                    "ic50_uM": None if pd.isna(ln) else float(math.exp(float(ln))),
                    "auc": None if pd.isna(row.get("AUC")) else float(row["AUC"]),
                    "z_score": None if pd.isna(row.get("Z_SCORE")) else float(row["Z_SCORE"]),
                    "rmse": None if pd.isna(row.get("RMSE")) else float(row["RMSE"]),
                    "max_conc": None if pd.isna(row.get("MAX_CONC")) else float(row["MAX_CONC"]),
                    "sequenced": bool(model_id in sequenced_models) if model_id else False,
                    "driver_mutations": sorted(mut_by_model.get(model_id, ())) if model_id else [],
                    "url": url,
                })
    log(f"      {len(measurements)} per-cell-line measurements, {len(summaries)} compound x "
        f"release summaries")
    return measurements, summaries


# ===========================================================================
# (c) PubMed / PMC
# ===========================================================================
def esearch(db: str, term: str, retmax: int, cache_name: str) -> tuple[list[str], int]:
    txt = cached_get(f"{EUTILS}/esearch.fcgi", None, cache_name, method="POST",
                     data={"db": db, "term": term, "retmode": "json", "retmax": retmax,
                           "email": cfg.NCBI_EMAIL, "tool": "ddr-scavenger"},
                     validate=no_ncbi_error)
    time.sleep(NCBI_SLEEP)
    res = load_json(txt)["esearchresult"]
    return res.get("idlist", []), int(res.get("count", 0))


def epost_fetch(db: str, ids: list[str], cache_name: str, retmode: str = "xml",
                util: str = "efetch") -> str:
    txt = cached_get(f"{EUTILS}/{util}.fcgi", None, cache_name, method="POST",
                     data={"db": db, "id": ",".join(ids), "retmode": retmode,
                           "email": cfg.NCBI_EMAIL, "tool": "ddr-scavenger"},
                     timeout=300, validate=no_ncbi_error)
    time.sleep(NCBI_SLEEP)
    return txt


def _text(node) -> str:
    return "".join(node.itertext()).strip() if node is not None else ""


PUBMED_RETMAX = 2000


def harvest_pubmed() -> list[dict]:
    """Fetch PubMed records for the non-WEE1 DDR compounds.

    The query is ``(any alias)[tiab] AND (biomarker-context terms)[tiab]``. That filter is
    a deliberate precision trade-off, recorded on every row: without it the PARP inhibitor
    literature alone runs to tens of thousands of papers, virtually none of which report a
    biomarker-response association. Exact retrieved-vs-available counts are logged so the
    coverage gap is measurable.
    """
    log("\n[c] PubMed (non-WEE1 DDR compounds) ...")
    wee1_canon = {c["canonical"] for c in cfg.ACTIVE_COMPOUNDS if c["target"] == "WEE1"}
    targets = [c for c in cfg.TEXT_MATCHABLE if c["canonical"] not in wee1_canon]
    log(f"      {len(targets)} compounds to search "
        f"({len(wee1_canon)} WEE1 compounds reused from the existing WEE1 harvest)")

    pmids: set[str] = set()
    coverage: list[dict] = []
    for c in targets:
        query = f"{cfg.pubmed_tiab_query(c)} AND {cfg.PUBMED_BIOMARKER_FILTER}"
        try:
            ids, total = esearch("pubmed", query, PUBMED_RETMAX,
                                 f"esearch_pubmed_{slug(c['canonical'])}.json")
        except RuntimeError as e:
            log(f"      !! esearch failed for {c['canonical']}: {e}")
            continue
        coverage.append({"compound": c["canonical"], "available": total, "retrieved": len(ids)})
        pmids |= set(ids)
        if total:
            flag = "  (TRUNCATED)" if total > len(ids) else ""
            log(f"        {c['canonical']:<20s} {len(ids):5d}/{total:5d} PMIDs{flag}")
    (DATA / "pubmed_coverage.json").write_text(
        json.dumps(coverage, indent=1), encoding="utf-8")
    log(f"      {len(pmids)} unique PMIDs to fetch")

    records: list[dict] = []
    for i, batch in enumerate(chunks(sorted(pmids), 200)):
        try:
            xml = epost_fetch("pubmed", batch, f"efetch_pubmed_{i}.xml")
            root = ET.fromstring(CONTROL_CHARS.sub(" ", xml))
        except Exception as e:  # noqa: BLE001
            log(f"      !! batch {i} unusable ({type(e).__name__}); skipped")
            continue
        for art in root.iter("PubmedArticle"):
            pmid = _text(art.find(".//PMID"))
            title = _text(art.find(".//ArticleTitle"))
            abstract = " ".join(_text(a) for a in art.findall(".//Abstract/AbstractText"))
            journal = _text(art.find(".//Journal/Title"))
            year = (_text(art.find(".//JournalIssue/PubDate/Year"))
                    or _text(art.find(".//JournalIssue/PubDate/MedlineDate"))[:4])
            authors = [f'{_text(a.find("LastName"))} {_text(a.find("Initials"))}'.strip()
                       for a in art.findall(".//Author")]
            first = (authors[0] + (" et al." if len(authors) > 1 else "")) if authors else ""
            doi = next((_text(a) for a in art.findall(".//ArticleId")
                        if a.get("IdType") == "doi"), "")
            ptypes = [_text(p) for p in art.findall(".//PublicationType")]
            mesh = [_text(m) for m in art.findall(".//MeshHeading/DescriptorName")]
            blob = f"{title} {abstract} {' '.join(mesh)}"
            drugs = cfg.find_compounds(blob, text_mode=True)
            if not drugs:
                continue
            records.append({
                "layer": "pubmed",
                "record_id": pmid,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "doi": doi or None,
                "drugs": drugs,
                "title": title,
                "abstract": abstract[:4000] or None,
                "journal": journal or None,
                "year": year or None,
                "first_author": first or None,
                "pub_types": ptypes,
                "mesh_cancer": [m for m in mesh if re.search(
                    r"neoplas|carcinom|sarcom|leukem|lymphom|glioma|melanom|myelom|tumou?r",
                    m, re.I)],
                "biomarkers": cfg.find_biomarkers(blob),
                "evidence_label": cfg.classify_evidence(blob, ptypes),
                "off_topic": cfg.off_topic_reason(blob),
                "source_note": "biomarker-context-filtered PubMed tiab query",
            })
        log(f"      batch {i}: cumulative {len(records)} records")
    log(f"      {len(records)} PubMed records kept")
    return records


def reuse_wee1_literature() -> list[dict]:
    """Re-use the existing WEE1 PubMed/PMC corpus instead of re-fetching it.

    PMC rows whose only match was in the full text (``match_scope`` = 'needs triage') are
    dropped: an inhibitor name appearing somewhere in a supplementary screening table is
    not evidence about that inhibitor.
    """
    log("\n[c2] Re-using the existing WEE1 literature corpus ...")
    path = WEE1_DATA / "harvest.json"
    if not path.exists():
        log(f"      !! {path} missing - skipping")
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    n_pubmed = n_pmc = n_pmc_dropped = 0
    out: list[dict] = []
    for r in raw:
        db = r.get("source_database")
        if db not in ("PubMed", "PubMed Central"):
            continue
        blob = f"{r.get('title', '')} {r.get('abstract_or_summary', '')}"
        drugs = cfg.find_compounds(blob, text_mode=True)
        if not drugs:
            continue
        if db == "PubMed Central":
            if "full text only" in (r.get("match_scope") or ""):
                n_pmc_dropped += 1
                continue
            n_pmc += 1
        else:
            n_pubmed += 1
        out.append({
            "layer": "pubmed" if db == "PubMed" else "pmc",
            "record_id": r.get("record_id"),
            "url": r.get("url"),
            "doi": None,
            "drugs": drugs,
            "title": r.get("title"),
            "abstract": (r.get("abstract_or_summary") or None),
            "journal": None,
            "year": (r.get("date") or "")[:4] or None,
            "first_author": r.get("attribution") or None,
            "pub_types": [],
            "mesh_cancer": [x.strip() for x in (r.get("indication") or "").split(";") if x.strip()],
            "biomarkers": cfg.find_biomarkers(blob),
            "evidence_label": r.get("evidence_type") or cfg.classify_evidence(blob),
            "off_topic": cfg.off_topic_reason(blob),
            "source_note": ("re-used from wee1_scavenger/data/harvest.json (unfiltered WEE1 "
                            "alias query)"),
        })
    log(f"      reused {n_pubmed} PubMed + {n_pmc} PMC (title-match) records; "
        f"dropped {n_pmc_dropped} PMC full-text-only matches")
    return out


# ===========================================================================
def main(layers: list[str]) -> None:
    out: dict[str, list] = {}
    if "ctgov" in layers:
        out["ctgov"] = harvest_clinicaltrials()
    if "gdsc" in layers:
        meas, summ = harvest_gdsc()
        out["gdsc"] = meas
        out["gdsc_summary"] = summ
    if "pubmed" in layers:
        out["literature"] = harvest_pubmed() + reuse_wee1_literature()

    path = DATA / "ddr_harvest.json"
    if path.exists() and set(layers) != {"ctgov", "gdsc", "pubmed"}:
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing.update(out)
        out = existing
    path.write_text(json.dumps(out, separators=(",", ":"), default=str), encoding="utf-8")
    log(f"\nwrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    for k, v in out.items():
        log(f"   {len(v):7d}  {k}")


if __name__ == "__main__":
    requested = [a for a in sys.argv[1:] if not a.startswith("-")]
    main(requested or ["ctgov", "gdsc", "pubmed"])
