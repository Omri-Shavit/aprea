"""Turn data/ddr_harvest.json into backend/data/ddr_evidence.json + ddr_compounds.json.

Contract
--------
Both outputs are plain JSON lists of flat objects whose keys are exactly the SQLModel
field names, so the backend can do ``Evidence(**row)`` / ``Compound(**row)``. Every row
is constructed through the real model classes before anything is written, and the script
aborts on the first mismatch.

Absolute rule enforced here
---------------------------
No value is invented. Each row is one of:

  * a value copied verbatim from a real source (ClinicalTrials.gov v2 JSON, a GDSC
    release-8.5 xlsx, a Cell Model Passports mutation call, a PubMed record), or
  * a label derived from such a value by a rule stated in this file and echoed into the
    row's ``notes``, or
  * a statistic this script genuinely computes from the real measurements, with the
    test, the group sizes and the dataset named in ``notes``.

Anything unknown is left NULL. ``effect_size``/``p_value``/``q_value`` are populated only
on the GDSC association rows, where they are computed here, and ``ci_low``/``ci_high``
only where ClinicalTrials.gov actually posted a confidence interval.

Row types produced
------------------
  registry_design      one per (trial x DDR agent x biomarker). Design/selection facts.
                       No response value: the registry reports none.
  registry_result      one per (trial x DDR agent x posted outcome measure x arm). Carries
                       a real reported efficacy value parsed from the resultsSection.
  gdsc_measurement     one per (GDSC release x drug x cell line). Real IC50, annotated
                       with the line's TP53 driver-mutation status where it was sequenced.
  gdsc_lineage_assoc   computed: Mann-Whitney U of LN_IC50, one lineage vs all others.
  gdsc_mutation_assoc  computed: Mann-Whitney U of LN_IC50, driver-mutant vs wild-type.
  literature           one per (paper x DDR agent x biomarker) - a keyword co-mention,
                       labelled as such and explicitly flagged as needing curation.

Usage
    python build_evidence.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import mannwhitneyu

import ddr_config as cfg

HERE = Path(__file__).parent
DATA = HERE / "data"
BACKEND = (HERE.parent / "Work for julie" / "wee1-evidence-app" / "backend").resolve()
OUT_DIR = BACKEND / "data"

sys.path.insert(0, str(BACKEND))
from models import Compound, Evidence  # noqa: E402
import vocabulary as vocab  # noqa: E402
from vocabulary import (  # noqa: E402
    TARGET_FAMILY, categorize_indication, endpoint_class_for,
)

# Fields whose values must appear in a backend/vocabulary.py list. The API validates
# filters against these lists, so a value outside them yields a row the UI cannot reach.
# response_metric is excluded on purpose: it uses the documented 'not_reported' sentinel
# for trials and papers that declare no efficacy endpoint.
VOCAB_FIELDS = {
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
    "specimen_timing": vocab.SPECIMEN_TIMINGS,
    "direction": vocab.DIRECTIONS,
    "evidence_tier": vocab.EVIDENCE_TIERS,
    "reproducibility": vocab.REPRODUCIBILITY,
    "predictive_vs_prognostic": vocab.PREDICTIVE_CLASSES,
    "evidence_basis": vocab.EVIDENCE_BASES,
    "target_specific_vs_combo": vocab.ATTRIBUTION,
    "baseline_vs_pd": vocab.BASELINE_VS_PD,
    "treatment_setting": vocab.TREATMENT_SETTINGS,
    "endpoint_class": vocab.ENDPOINT_CLASSES,
}

# GDSC release 8.5 fitted dose-response files are dated 27 Oct 2023 (the filename of the
# release actually downloaded), so that is the year recorded on GDSC-derived rows.
GDSC_RELEASE = "GDSC release 8.5 (27 Oct 2023)"
GDSC_RELEASE_YEAR = 2023
CMP_RELEASE = "Cell Model Passports mutations_summary_20230202"

# Z_SCORE is GDSC's own standardisation of LN_IC50 across the cell lines screened with
# that compound. These cut-offs are a labelling convention applied to the real value, and
# every row that uses them says so.
Z_SENSITIVE, Z_RESISTANT = -1.0, 1.0

# Minimum group sizes for an association test to be run at all.
MIN_GROUP_LINEAGE = 10
MIN_GROUP_MUTATION = 12
# A driver gene must be mutated in at least this many sequenced models overall to enter
# the hypothesis panel.
MIN_GLOBAL_MUTANT_MODELS = 15
FDR_ALPHA = 0.10

# Compounds whose own annotation says the phenotype cannot be attributed to the nominal
# DDR target. Used to set target_specific_vs_combo honestly even for monotherapy rows.
NOT_TARGET_ATTRIBUTABLE = {
    "torin2", "QL-VIII-58", "voxtalisib", "CC-115", "iniparib", "CYT-0851", "harmine",
    "novobiocin", "AZD7762", "PD0166285", "PD407824", "stenoparib", "TANK_1366",
}

# Driver genes tested for a sensitivity association. Hypothesis-driven rather than
# all-genes: restricting to DDR and canonical-driver genes keeps the multiple-testing
# burden on comparisons that have a mechanistic rationale. Intersected at run time with
# the genes actually mutated in >= MIN_GLOBAL_MUTANT_MODELS sequenced models.
DRIVER_PANEL = [
    "TP53", "KRAS", "NRAS", "BRAF", "PIK3CA", "PIK3R1", "PTEN", "RB1", "CDKN2A",
    "ARID1A", "SMARCA4", "STK11", "KEAP1", "NF1", "APC", "FBXW7", "SMAD4", "CTNNB1",
    "EGFR", "ERBB2", "MET", "NOTCH1", "MYC", "MYCN", "CCNE1", "CDK12", "TERT",
    "BRCA1", "BRCA2", "ATM", "ATR", "ATRX", "CHEK2", "PALB2", "RAD51C", "RAD51D",
    "BARD1", "BRIP1", "FANCA", "FANCM", "POLE", "POLD1", "POLQ", "MSH2", "MSH6",
    "MLH1", "PMS2", "ERCC2", "WRN", "BLM", "NBN", "MRE11", "SETD2", "KMT2C", "KMT2D",
    "CREBBP", "EP300", "PPP2R1A", "TP53BP1", "USP1", "WEE1", "PKMYT1", "BAP1",
]

# GDSC tissue descriptors -> OncoTree-style indication labels. This is a vocabulary
# alignment, not new data: the left-hand side is the verbatim GDSC "Tissue descriptor 2"
# value and the raw value is preserved in `histology` on every row. It exists because
# backend/vocabulary.py keys on clinical wording ("ovarian", "colorectal") that the GDSC
# anatomical wording ("ovary", "large_intestine") does not contain.
GDSC_TISSUE_TO_INDICATION = {
    "lung_NSCLC_adenocarcinoma": "Lung adenocarcinoma (NSCLC)",
    "lung_NSCLC_squamous_cell_carcinoma": "Lung squamous cell carcinoma (NSCLC)",
    "lung_NSCLC_large cell": "Large cell lung carcinoma (NSCLC)",
    "lung_NSCLC_not specified": "Non-small cell lung cancer",
    "lung_NSCLC_carcinoid": "Lung carcinoid tumor",
    "lung_small_cell_carcinoma": "Small cell lung cancer",
    "Lung_other": "Lung cancer, other",
    "mesothelioma": "Mesothelioma",
    "large_intestine": "Colorectal cancer",
    "digestive_system_other": "Gastrointestinal cancer, other",
    "oesophagus": "Esophageal cancer",
    "stomach": "Gastric cancer",
    "pancreas": "Pancreatic cancer",
    "liver": "Hepatocellular carcinoma",
    "biliary_tract": "Biliary tract / cholangiocarcinoma",
    "ovary": "Ovarian cancer",
    "cervix": "Cervical cancer",
    "endometrium": "Endometrial cancer",
    "uterus": "Uterine cancer",
    "breast": "Breast cancer",
    "kidney": "Renal cell carcinoma",
    "Bladder": "Bladder / urothelial carcinoma",
    "prostate": "Prostate cancer",
    "testis": "Testicular germ cell tumor",
    "urogenital_system_other": "Genitourinary cancer, other",
    "adrenal_gland": "Adrenocortical carcinoma",
    "thyroid": "Thyroid cancer",
    "head and neck": "Head and neck squamous cell carcinoma",
    "glioma": "Glioma",
    "medulloblastoma": "Medulloblastoma",
    "neuroblastoma": "Neuroblastoma",
    "melanoma": "Melanoma",
    "skin_other": "Cutaneous malignancy, other",
    "osteosarcoma": "Osteosarcoma",
    "ewings_sarcoma": "Ewing sarcoma",
    "chondrosarcoma": "Chondrosarcoma",
    "rhabdomyosarcoma": "Rhabdomyosarcoma",
    "fibrosarcoma": "Fibrosarcoma",
    "soft_tissue_other": "Soft tissue sarcoma, other",
    "bone_other": "Bone sarcoma, other",
    "acute_myeloid_leukaemia": "Acute myeloid leukemia",
    "chronic_myeloid_leukaemia": "Chronic myeloid leukemia",
    "lymphoblastic_leukemia": "Acute lymphoblastic leukemia",
    "lymphoblastic_T_cell_leukaemia": "T-cell acute lymphoblastic leukemia",
    "B_cell_leukemia": "B-cell leukemia",
    "T_cell_leukemia": "T-cell leukemia",
    "hairy_cell_leukaemia": "Hairy cell leukemia",
    "leukemia": "Leukemia, other",
    "B_cell_lymphoma": "B-cell lymphoma",
    "Burkitt_lymphoma": "Burkitt lymphoma",
    "Hodgkin_lymphoma": "Hodgkin lymphoma",
    "anaplastic_large_cell_lymphoma": "Anaplastic large cell lymphoma",
    "lymphoid_neoplasm other": "Lymphoid neoplasm, other",
    "haematopoietic_neoplasm other": "Hematopoietic neoplasm, other",
    "myeloma": "Multiple myeloma",
}

PHASE_FROM_RANK = {0: "phase_1", 1: "phase_1", 2: "phase_2", 3: "phase_3", 4: "phase_3"}

ROWS: list[dict] = []
STATS = Counter()


def log(msg: str) -> None:
    print(msg, flush=True)


# ===========================================================================
# helpers
# ===========================================================================
def benjamini_hochberg(pvals: list[float]) -> list[float]:
    """Standard BH step-up FDR. Returns q-values in the input order."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = m - rank + 1  # 1-based rank of this p-value ascending
        val = min(1.0, pvals[idx] * m / i)
        prev = min(prev, val)
        q[idx] = prev
    return q


def cohens_d(a: list[float], b: list[float]) -> float | None:
    """Pooled-SD Cohen's d for group a vs group b (negative = a lower than b)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    pooled = ((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)
    if pooled <= 0:
        return None
    return (ma - mb) / math.sqrt(pooled)


def rank_biserial(u_stat: float, n1: int, n2: int) -> float:
    """Rank-biserial correlation from the Mann-Whitney U of group 1."""
    return 2.0 * u_stat / (n1 * n2) - 1.0


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def alias_as_written(compound: str, *texts) -> str | None:
    """Which of the compound's aliases the source actually used."""
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    for a in cfg.BY_CANONICAL[compound]["aliases"]:
        if re.search(cfg._alias_pattern(a), blob, re.I):
            return a
    return None


def biomarker_fields(name: str) -> tuple[str, str | None]:
    """(biomarker_type, biomarker_scope) for a vocabulary biomarker or a placeholder."""
    if name in cfg.BIOMARKER_TYPE:
        return cfg.BIOMARKER_TYPE[name], cfg.BIOMARKER_SCOPE[name]
    return "signature", None


def is_pd_marker(name: str) -> bool:
    return "pharmacodynamic" in name


def attribution_for(compound: str, is_mono: bool) -> str:
    if compound in NOT_TARGET_ATTRIBUTABLE:
        return "unclear"
    return "target_specific" if is_mono else "unclear"


def indication_for_tissue(tissue_detail: str | None, tcga: str | None) -> tuple[str, str]:
    if tissue_detail and tissue_detail in GDSC_TISSUE_TO_INDICATION:
        label = GDSC_TISSUE_TO_INDICATION[tissue_detail]
    elif tissue_detail:
        label = tissue_detail.replace("_", " ")
    elif tcga and tcga.upper() not in ("UNCLASSIFIED", "NAN"):
        label = f"TCGA {tcga}"
    else:
        label = "not specified"
    return label, categorize_indication(label)


def add(**row) -> None:
    ROWS.append(row)


# ===========================================================================
# 1. Compound dictionary
# ===========================================================================
def build_compounds(ctgov: list[dict]) -> list[dict]:
    log("\n[1] Compound dictionary ...")
    trials_by_compound: dict[str, list[dict]] = defaultdict(list)
    for r in ctgov:
        for d in r["drugs"]:
            trials_by_compound[d].append(r)

    out: list[dict] = []
    for c in cfg.ACTIVE_COMPOUNDS:
        canon = c["canonical"]
        if c["target"] not in TARGET_FAMILY:
            raise AssertionError(f"{canon}: target {c['target']!r} not in vocabulary.TARGET_FAMILY")
        if TARGET_FAMILY[c["target"]] != cfg.TARGET_FAMILY[c["target"]]:
            raise AssertionError(f"target_family disagreement for {c['target']!r}")

        trials = trials_by_compound.get(canon, [])
        ranks = [t["max_phase_rank"] for t in trials if t["max_phase_rank"] is not None]
        curated = c["clinical_stage"]
        provenance_bits = []
        if curated == "approved":
            stage = "approved"
            provenance_bits.append("clinical_stage 'approved' is a curated regulatory fact")
        elif ranks:
            stage = PHASE_FROM_RANK[max(ranks)]
            provenance_bits.append(
                f"clinical_stage derived from the highest phase across "
                f"{len(trials)} ClinicalTrials.gov record(s)")
        else:
            stage = curated
            provenance_bits.append(f"clinical_stage is the curated value ({curated}); "
                                   "no ClinicalTrials.gov record names this compound")
        if trials:
            provenance_bits.append(f"{len(trials)} registry trial(s) harvested")
        provenance_bits.append(f"dictionary source: {c['source_of_record']}")

        aliases = [a for a in c["aliases"] if a.lower() != canon.lower()]
        out.append({
            "canonical_name": canon,
            "aliases": "; ".join(aliases) or None,
            "target": c["target"],
            "target_family": TARGET_FAMILY[c["target"]],
            "secondary_targets": c["secondary_targets"],
            "developer": c["developer"],
            "clinical_stage": stage,
            "selectivity": c["selectivity"],
            "off_target_activity": c["off_target"],
            # Dose/schedule are properties of a regimen, not of a molecule; they are
            # carried on Evidence rows where a real source stated them.
            "typical_dose": None,
            "typical_schedule": None,
            "chembl_id": c["chembl"],
            "is_tool_compound": bool(c["is_tool"]),
            "notes": ((c["notes"] + " " if c["notes"] else "") + " | ".join(provenance_bits)),
        })
    log(f"      {len(out)} compound rows "
        f"({sum(1 for r in out if r['is_tool_compound'])} tool compounds)")
    log(f"      {sum(1 for r in out if trials_by_compound.get(r['canonical_name']))} of them "
        f"have at least one harvested trial")
    return out


# ===========================================================================
# 2. Registry rows
# ===========================================================================
def metric_from_outcomes(primary: list[str], secondary: list[str]) -> tuple[str, str | None]:
    """Best controlled response_metric for a trial's declared endpoints."""
    for text in primary:
        m = cfg.map_outcome_metric(text)
        if m:
            return m, "primary"
    for text in secondary:
        m = cfg.map_outcome_metric(text)
        if m:
            return m, "secondary"
    # Many phase 1 studies declare only safety / DLT / PK endpoints. Recording
    # "not_reported" is honest; inventing ORR would not be.
    return cfg.METRIC_NOT_REPORTED, None


def build_registry(ctgov: list[dict]) -> None:
    log("\n[2] ClinicalTrials.gov rows ...")
    n_design = n_result = 0
    for r in ctgov:
        nct = r["record_id"]
        year = int(r["start_date"][:4]) if (r["start_date"] or "")[:4].isdigit() else None
        indication = "; ".join(r["conditions"])[:400] or "not specified"
        ind_cat = categorize_indication(indication)
        track, partner_target = cfg.classify_combination(r["partners"])
        real_partners = [p for p in r["partners"] if not cfg.is_non_therapeutic(p)]
        is_mono = track == "monotherapy"
        metric, metric_src = metric_from_outcomes(r["primary_outcomes"], r["secondary_outcomes"])
        randomized = (r["allocation"] or "").upper() == "RANDOMIZED"
        pop = (f"{r['phase_label']}; status {r['status']}; "
               f"enrollment {r['enrollment']} ({r['enrollment_type']})")

        design_bm = sorted(set(r["biomarkers_design"]) | set(r["biomarkers_outcomes"]))
        elig_bm = [b for b in r["biomarkers_eligibility"] if b not in design_bm]

        for canon in r["drugs"]:
            spec = cfg.BY_CANONICAL[canon]
            dose_info = (r["dose_by_drug"] or {}).get(canon) or {}
            alias = alias_as_written(canon, r["drug_name_as_written"], r["title"],
                                     r["official_title"])
            base = {
                "source_type": "registry",
                "citation": f"{r['sponsor'] or 'sponsor not stated'}. {r['title']}"[:900],
                "url_or_doi": r["url"],
                "dataset_id": nct,
                "year": year,
                "target": spec["target"],
                "target_family": TARGET_FAMILY[spec["target"]],
                "compound": canon,
                "alias": alias,
                "dose": dose_info.get("dose"),
                "schedule": dose_info.get("schedule"),
                "combination_track": track,
                "combo_partner": "; ".join(real_partners)[:300] or None,
                "combo_partner_target": partner_target,
                "is_monotherapy": is_mono,
                "indication": indication,
                "indication_category": ind_cat,
                "histology": None,
                "treatment_setting": r["treatment_setting"],
                "prior_therapies": None,
                "model_type": "patient",
                "perturbation_type": "chemical",
                "specimen_type": r["specimen_type"],
                "specimen_timing": r["specimen_timing"],
                "evidence_tier": "clinical",
                "predictive_vs_prognostic": "unclear",
                "target_specific_vs_combo": attribution_for(canon, is_mono),
            }

            # ---- design rows: one per biomarker the trial is built around / screens on
            entries = ([(b, "design") for b in design_bm] + [(b, "eligibility") for b in elig_bm]
                       or [(cfg.NO_BIOMARKER_TRIAL, "none")])
            for bm, where in entries:
                btype, bscope = biomarker_fields(bm)
                if where == "none":
                    note = ("Trial-design record. The registry entry names no biomarker from the "
                            "controlled vocabulary anywhere in its title, arms, conditions, "
                            "outcome measures or eligibility criteria, so this row carries the "
                            "documented placeholder and represents an unselected population.")
                else:
                    note = (f"Trial-design record. Biomarker detected by regular-expression "
                            f"co-mention in the registry entry's "
                            f"{'title/arms/conditions/outcome measures' if where == 'design' else 'eligibility criteria'}"
                            f"; this is NOT a curated selection criterion and must be verified "
                            f"against the protocol before use.")
                note += (" No outcome is reported for this row, so no effect size, p-value or "
                         "direction is claimed. Fields left NULL are not reported by the registry.")
                if r["has_results"] and not r["posted_results"]:
                    note += (" The study has posted results, but none of its outcome measures "
                             "mapped unambiguously onto the controlled endpoint vocabulary, so "
                             "no value was parsed.")
                note += f" Allocation: {r['allocation'] or 'not stated'}."
                add(**base,
                    biomarker_name=bm,
                    biomarker_type=btype,
                    biomarker_scope=bscope,
                    assay=None, assay_modality=None, cutoff=None, biomarker_status=None,
                    model_id=None,
                    n=r["enrollment"],
                    population_description=pop,
                    response_metric=metric,
                    response_value=None,
                    units=None,
                    endpoint_class=(None if metric == cfg.METRIC_NOT_REPORTED
                                    else endpoint_class_for(metric)),
                    direction=None,
                    effect_size=None, effect_size_type=None, p_value=None, q_value=None,
                    ci_low=None, ci_high=None,
                    reproducibility=None,
                    # No claim: a design record with no result supports no evidence basis.
                    evidence_basis=None,
                    baseline_vs_pd=("pharmacodynamic" if is_pd_marker(bm) else "baseline"),
                    notes=note[:1900])
                n_design += 1

            # ---- result rows: real posted efficacy values
            # The result applies to a whole arm. It is attributed to a specific biomarker
            # only when the trial was designed around exactly one, otherwise it gets the
            # unselected-population placeholder.
            res_bm = design_bm[0] if len(design_bm) == 1 else cfg.NO_BIOMARKER_TRIAL
            res_btype, res_bscope = biomarker_fields(res_bm)
            for pr in r["posted_results"]:
                add(**base,
                    biomarker_name=res_bm,
                    biomarker_type=res_btype,
                    biomarker_scope=res_bscope,
                    assay=None, assay_modality=None, cutoff=None, biomarker_status=None,
                    model_id=pr["group_title"][:200] or None,
                    n=pr["group_n"],
                    population_description=(f"{pr['group_title']}. "
                                            f"{pr['population_description']}".strip())[:900],
                    response_metric=pr["metric"],
                    response_value=pr["value"],
                    units=pr["units"] or None,
                    endpoint_class=endpoint_class_for(pr["metric"]),
                    direction=None,
                    effect_size=None, effect_size_type=None, p_value=None, q_value=None,
                    ci_low=pr["ci_low"], ci_high=pr["ci_high"],
                    reproducibility="single_dataset",
                    evidence_basis="single_arm_association",
                    baseline_vs_pd=("pharmacodynamic" if is_pd_marker(res_bm) else "baseline"),
                    notes=(
                        f"Reported result parsed from the ClinicalTrials.gov v2 resultsSection. "
                        f"Outcome measure: '{pr['measure_title']}' ({pr['measure_type']}, "
                        f"paramType={pr['param_type']}, unit '{pr['units']}', time frame "
                        f"'{pr['time_frame']}'). Arm: '{pr['group_title']}'. The value and any "
                        f"confidence interval are exactly as posted by the sponsor. "
                        f"Allocation: {r['allocation'] or 'not stated'}. This is a within-arm "
                        f"result: the registry reports no biomarker-by-treatment interaction, "
                        f"so it cannot establish predictiveness."
                    )[:1900])
                n_result += 1
    STATS["registry_design"] = n_design
    STATS["registry_result"] = n_result
    log(f"      {n_design} design rows, {n_result} reported-result rows")


# ===========================================================================
# 3. GDSC rows
# ===========================================================================
def build_gdsc_measurements(meas: list[dict]) -> None:
    log("\n[3] GDSC per-cell-line rows ...")
    releases_by_compound: dict[str, set[str]] = defaultdict(set)
    for m in meas:
        releases_by_compound[m["canonical"]].add(m["release"])

    n = 0
    for m in meas:
        if m["ic50_uM"] is None or m["cell_line"] is None:
            continue
        canon = m["canonical"]
        spec = cfg.BY_CANONICAL[canon]
        indication, ind_cat = indication_for_tissue(m["tissue_detail"], m["tcga_desc"])
        z = m["z_score"]
        if z is None:
            direction = None
        elif z <= Z_SENSITIVE:
            direction = "sensitive"
        elif z >= Z_RESISTANT:
            direction = "resistant"
        else:
            direction = "neutral"

        if m["sequenced"]:
            tp53 = "TP53" in m["driver_mutations"]
            bm_name = "TP53 driver mutation"
            bm_type, bm_scope, bm_status = "mutation", "tumor_agnostic", (
                "positive" if tp53 else "negative")
            assay = "WES driver call (Cell Model Passports 20230202)"
            assay_modality = "ngs"
            cutoff = "driver mutation present vs absent"
            bm_note = f"TP53 status from {CMP_RELEASE}, joined on SANGER_MODEL_ID."
        else:
            bm_name = cfg.NO_BIOMARKER_CELL_LINE
            bm_type, bm_scope, bm_status = "signature", None, None
            assay = assay_modality = cutoff = None
            bm_note = "No exome sequencing in Cell Model Passports; no mutation status asserted."

        add(source_type="database",
            citation=(f"GDSC {GDSC_RELEASE}: {m['drug_name']} "
                      f"(DRUG_ID {m['drug_id']}) in {m['cell_line']}"),
            url_or_doi=m["url"],
            dataset_id=f"{m['release']}:{m['drug_id']}",
            year=GDSC_RELEASE_YEAR,
            target=spec["target"],
            target_family=TARGET_FAMILY[spec["target"]],
            compound=canon,
            alias=m["drug_name"],
            dose=None,
            schedule=None,
            combination_track="monotherapy",
            combo_partner=None,
            combo_partner_target=None,
            is_monotherapy=True,
            indication=indication,
            indication_category=ind_cat,
            histology=(f"GDSC tissue: {m['tissue_detail'] or 'n/a'} / "
                       f"TCGA_DESC {m['tcga_desc'] or 'n/a'}"),
            treatment_setting="n/a (preclinical)",
            prior_therapies=None,
            model_type="cell_line",
            model_id=m["cell_line"],
            n=1,
            population_description=(f"cell line {m['cell_line']} (COSMIC {m['cosmic_id']}, "
                                    f"Sanger {m['sanger_model_id']})"),
            perturbation_type="chemical",
            specimen_type="cell_pellet",
            specimen_timing="baseline",
            biomarker_name=bm_name,
            biomarker_type=bm_type,
            biomarker_scope=bm_scope,
            assay=assay,
            assay_modality=assay_modality,
            cutoff=cutoff,
            biomarker_status=bm_status,
            response_metric="IC50",
            response_value=round(m["ic50_uM"], 6),
            units="uM",
            endpoint_class=endpoint_class_for("IC50"),
            direction=direction,
            effect_size=None, effect_size_type=None, p_value=None, q_value=None,
            ci_low=None, ci_high=None,
            evidence_tier="preclinical_invitro",
            reproducibility=("multi_dataset" if len(releases_by_compound[canon]) > 1
                             else "single_dataset"),
            predictive_vs_prognostic=None,
            # A single measurement is not an association, so no evidence basis is claimed.
            evidence_basis=None,
            target_specific_vs_combo=attribution_for(canon, True),
            baseline_vs_pd="baseline",
            notes=(
                f"{m['release']} single fitted dose-response, {GDSC_RELEASE}. "
                f"response_value = exp(LN_IC50) uM from the published LN_IC50={m['ln_ic50']:.4f}; "
                f"AUC={m['auc']}; Z_SCORE={m['z_score']}; MAX_CONC={m['max_conc']} uM; "
                f"RMSE={m['rmse']}. direction labels the real Z_SCORE "
                f"(<={Z_SENSITIVE} sensitive, >={Z_RESISTANT} resistant, else neutral). "
                f"{bm_note} Do not pool GDSC1 with GDSC2 - separate assay generations."
            )[:1900])
        n += 1
    STATS["gdsc_measurement"] = n
    log(f"      {n} per-cell-line measurement rows")


def _run_tests(groups: list[tuple[dict, list[float], list[float]]]) -> list[dict]:
    """Mann-Whitney U + Cohen's d for each (meta, in-group, out-group) triple, then BH."""
    results = []
    for meta, ins, outs in groups:
        u, p = mannwhitneyu(ins, outs, alternative="two-sided")
        d = cohens_d(ins, outs)
        if d is None or p != p:  # NaN guard
            continue
        results.append({**meta, "n_in": len(ins), "n_out": len(outs), "u": float(u),
                        "p": float(p), "d": d,
                        "rb": rank_biserial(float(u), len(ins), len(outs)),
                        "median_ic50_in": math.exp(median(ins)),
                        "median_ic50_out": math.exp(median(outs))})
    qs = benjamini_hochberg([r["p"] for r in results])
    for r, q in zip(results, qs):
        r["q"] = q
    return results


def _assoc_row(res: dict, kind: str, bm_name: str, bm_type: str, bm_scope: str,
               assay: str, assay_modality: str, cutoff: str | None,
               bm_status: str | None, indication: str, ind_cat: str, histology: str | None,
               reproducibility: str, extra_note: str) -> None:
    canon = res["canonical"]
    spec = cfg.BY_CANONICAL[canon]
    direction = "sensitive" if res["d"] < 0 else ("resistant" if res["d"] > 0 else "neutral")
    add(source_type="database",
        citation=(f"Computed from Genomics of Drug Sensitivity in Cancer, {GDSC_RELEASE}: "
                  f"{res['drug_name']} (GDSC DRUG_ID {res['drug_id']}, {res['release']})"),
        url_or_doi=res["url"],
        dataset_id=f"{res['release']}:{res['drug_id']}",
        year=GDSC_RELEASE_YEAR,
        target=spec["target"],
        target_family=TARGET_FAMILY[spec["target"]],
        compound=canon,
        alias=res["drug_name"],
        dose=None, schedule=None,
        combination_track="monotherapy",
        combo_partner=None, combo_partner_target=None, is_monotherapy=True,
        indication=indication,
        indication_category=ind_cat,
        histology=histology,
        treatment_setting="n/a (preclinical)",
        prior_therapies=None,
        model_type="cell_line",
        model_id=None,
        n=res["n_in"] + res["n_out"],
        population_description=(f"{res['n_in']} cell lines in the tested group vs "
                               f"{res['n_out']} comparator cell lines, all screened with "
                               f"{res['drug_name']} in {res['release']}"),
        perturbation_type="chemical",
        specimen_type="cell_pellet",
        specimen_timing="baseline",
        biomarker_name=bm_name,
        biomarker_type=bm_type,
        biomarker_scope=bm_scope,
        assay=assay,
        assay_modality=assay_modality,
        cutoff=cutoff,
        biomarker_status=bm_status,
        response_metric="IC50",
        response_value=round(res["median_ic50_in"], 6),
        units="uM",
        endpoint_class=endpoint_class_for("IC50"),
        direction=direction,
        effect_size=round(res["d"], 6),
        effect_size_type="cohens_d",
        p_value=res["p"],
        q_value=res["q"],
        ci_low=None, ci_high=None,
        evidence_tier="preclinical_invitro",
        reproducibility=reproducibility,
        predictive_vs_prognostic="unclear",
        evidence_basis="preclinical_correlation",
        target_specific_vs_combo=attribution_for(canon, True),
        baseline_vs_pd="baseline",
        notes=(
            f"COMPUTED STATISTIC, not a value copied from a publication. Two-sided "
            f"Mann-Whitney U test on LN_IC50 from {GDSC_RELEASE} ({res['release']} arm) for "
            f"{res['drug_name']} (GDSC DRUG_ID {res['drug_id']}): {res['n_in']} cell lines in "
            f"the tested group vs {res['n_out']} others. U = {res['u']:.1f}, p = {res['p']:.3g}. "
            f"effect_size is Cohen's d on LN_IC50 = {res['d']:.3f} (negative = the tested group "
            f"is more sensitive); rank-biserial correlation = {res['rb']:.3f}. q_value is a "
            f"Benjamini-Hochberg FDR correction across all {kind} tests in this build. "
            f"Median IC50 {res['median_ic50_in']:.3f} uM in the tested group vs "
            f"{res['median_ic50_out']:.3f} uM in the comparator. response_value is the tested "
            f"group's median IC50. `direction` is the sign of the observed effect; significance "
            f"is carried by p_value/q_value. {extra_note} This is an unadjusted marginal "
            f"association: it is not controlled for lineage, growth rate or any other covariate."
        )[:1900])


def build_gdsc_lineage(meas: list[dict]) -> None:
    log("\n[4] GDSC computed lineage associations ...")
    by_drug: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for m in meas:
        if m["ln_ic50"] is not None and m["tissue_detail"]:
            by_drug[(m["release"], m["drug_id"])].append(m)

    groups = []
    for (release, drug_id), rows in sorted(by_drug.items()):
        by_tissue: dict[str, list[float]] = defaultdict(list)
        for m in rows:
            by_tissue[m["tissue_detail"]].append(m["ln_ic50"])
        for tissue, vals in sorted(by_tissue.items()):
            others = [v for t, vs in by_tissue.items() if t != tissue for v in vs]
            if len(vals) < MIN_GROUP_LINEAGE or len(others) < MIN_GROUP_LINEAGE:
                continue
            groups.append(({
                "release": release, "drug_id": drug_id, "tissue": tissue,
                "canonical": rows[0]["canonical"], "drug_name": rows[0]["drug_name"],
                "url": rows[0]["url"],
            }, vals, others))

    results = _run_tests(groups)
    log(f"      {len(results)} lineage tests run "
        f"(min group size {MIN_GROUP_LINEAGE} per side)")

    # Reproducibility: was the same compound x lineage association seen, with the same
    # direction and q < FDR_ALPHA, in both GDSC releases?
    sig_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    tested_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in results:
        tested_key[(r["canonical"], r["tissue"])].add(r["release"])
        if r["q"] < FDR_ALPHA:
            sign = "sens" if r["d"] < 0 else "res"
            sig_key[(r["canonical"], r["tissue"], sign)].add(r["release"])

    n_sig = 0
    for r in results:
        sign = "sens" if r["d"] < 0 else "res"
        if len(sig_key[(r["canonical"], r["tissue"], sign)]) > 1:
            repro = "reproducible"
        elif len(tested_key[(r["canonical"], r["tissue"])]) > 1:
            repro = "multi_dataset"
        else:
            repro = "single_dataset"
        label, ind_cat = indication_for_tissue(r["tissue"], None)
        _assoc_row(
            r, kind="GDSC lineage", bm_name=f"{label} lineage",
            bm_type="signature", bm_scope="tumor_specific",
            assay="GDSC fitted dose-response (LN_IC50); lineage from the GDSC cell-line "
                  "annotation workbook 'GDSC Tissue descriptor 2'",
            assay_modality="functional",
            cutoff=None, bm_status=None,
            indication=label, ind_cat=ind_cat,
            histology=f"GDSC tissue descriptor: {r['tissue']}",
            reproducibility=repro,
            extra_note=(f"Tested group = cell lines annotated '{r['tissue']}'; comparator = all "
                        f"other lines screened with this compound in the same release. "
                        f"reproducibility='{repro}' was computed by checking whether the same "
                        f"compound x lineage association reached q<{FDR_ALPHA} with the same "
                        f"direction in both GDSC1 and GDSC2."))
        if r["q"] < FDR_ALPHA:
            n_sig += 1
    STATS["gdsc_lineage_assoc"] = len(results)
    STATS["gdsc_lineage_assoc_sig"] = n_sig
    log(f"      {n_sig} of {len(results)} survive BH FDR < {FDR_ALPHA}")


def build_gdsc_mutation(meas: list[dict]) -> None:
    log("\n[5] GDSC computed driver-mutation associations ...")
    # Global mutant-model counts across the sequenced models in this measurement set.
    mut_by_model: dict[str, list[str]] = {}
    for m in meas:
        if m["sequenced"] and m["sanger_model_id"]:
            mut_by_model.setdefault(m["sanger_model_id"], m["driver_mutations"])
    global_counts = Counter(g for v in mut_by_model.values() for g in v)
    panel = [g for g in DRIVER_PANEL if global_counts[g] >= MIN_GLOBAL_MUTANT_MODELS]
    log(f"      hypothesis panel: {len(panel)} of {len(DRIVER_PANEL)} curated driver genes are "
        f"mutated in >= {MIN_GLOBAL_MUTANT_MODELS} of the {len(mut_by_model)} sequenced models")
    log(f"        {', '.join(panel)}")

    by_drug: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for m in meas:
        if m["ln_ic50"] is not None and m["sequenced"] and m["sanger_model_id"]:
            by_drug[(m["release"], m["drug_id"])].append(m)

    groups = []
    for (release, drug_id), rows in sorted(by_drug.items()):
        for gene in panel:
            ins = [m["ln_ic50"] for m in rows if gene in m["driver_mutations"]]
            outs = [m["ln_ic50"] for m in rows if gene not in m["driver_mutations"]]
            if len(ins) < MIN_GROUP_MUTATION or len(outs) < MIN_GROUP_MUTATION:
                continue
            groups.append(({
                "release": release, "drug_id": drug_id, "gene": gene,
                "canonical": rows[0]["canonical"], "drug_name": rows[0]["drug_name"],
                "url": rows[0]["url"],
            }, ins, outs))

    results = _run_tests(groups)
    log(f"      {len(results)} mutation tests run "
        f"(min group size {MIN_GROUP_MUTATION} per side)")

    sig_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    tested_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in results:
        tested_key[(r["canonical"], r["gene"])].add(r["release"])
        if r["q"] < FDR_ALPHA:
            sig_key[(r["canonical"], r["gene"], "sens" if r["d"] < 0 else "res")].add(r["release"])

    n_sig = 0
    for r in results:
        sign = "sens" if r["d"] < 0 else "res"
        if len(sig_key[(r["canonical"], r["gene"], sign)]) > 1:
            repro = "reproducible"
        elif len(tested_key[(r["canonical"], r["gene"])]) > 1:
            repro = "multi_dataset"
        else:
            repro = "single_dataset"
        _assoc_row(
            r, kind="GDSC driver-mutation", bm_name=f"{r['gene']} driver mutation",
            bm_type="mutation", bm_scope="tumor_agnostic",
            assay=f"GDSC fitted dose-response (LN_IC50) vs whole-exome driver-mutation calls "
                  f"from {CMP_RELEASE}, joined on SANGER_MODEL_ID",
            assay_modality="ngs",
            cutoff="driver mutation called (present) vs not called (absent)",
            bm_status="positive",
            indication="pan-cancer cell line panel",
            ind_cat="pan_cancer",
            histology=None,
            reproducibility=repro,
            extra_note=(f"Tested group = cell lines with a called {r['gene']} driver mutation; "
                        f"comparator = sequenced cell lines without one. Only models with exome "
                        f"sequencing in Cell Model Passports are included, so an unsequenced line "
                        f"is never counted as wild-type. reproducibility='{repro}' was computed "
                        f"by checking whether the same compound x gene association reached "
                        f"q<{FDR_ALPHA} with the same direction in both GDSC1 and GDSC2."))
        if r["q"] < FDR_ALPHA:
            n_sig += 1
    STATS["gdsc_mutation_assoc"] = len(results)
    STATS["gdsc_mutation_assoc_sig"] = n_sig
    STATS["_panel"] = len(panel)
    log(f"      {n_sig} of {len(results)} survive BH FDR < {FDR_ALPHA}")


# ===========================================================================
# 6. Literature rows
# ===========================================================================
GENETIC_RX = re.compile(r"\b(CRISPR|siRNA|shRNA|knockdown|knockout|gene[\-\s]?trap)\b", re.I)


def build_literature(lit: list[dict]) -> None:
    log("\n[6] Literature rows ...")
    n = 0
    skipped_no_bm = 0
    skipped_off_topic = 0
    for r in lit:
        # Records with no oncology context are dropped, not annotated. They are
        # overwhelmingly the pre-oncology literature of repurposed molecules
        # (novobiocin as an antibacterial, harmine as an MAO inhibitor), where a
        # biomarker co-mention carries no information about cancer biology.
        if r["off_topic"]:
            skipped_off_topic += 1
            continue
        if not r["biomarkers"]:
            skipped_no_bm += 1
            continue
        year = int(r["year"]) if (r["year"] or "").isdigit() else None
        tier = cfg.evidence_tier_from_classification(r["evidence_label"] or "")
        label = r["evidence_label"] or ""
        if "Clinical" in label:
            model_type, setting = "patient", None
        elif "In vivo" in label:
            model_type, setting = "xenograft", "n/a (preclinical)"
        else:
            model_type, setting = "cell_line", "n/a (preclinical)"
        indication = "; ".join(r["mesh_cancer"])[:400] or "not specified"
        source_type = "peer_reviewed"
        dataset_id = r["record_id"]
        title_parts = re.split(r"\bwith\b|\bplus\b|\bin combination\b|\band\b|\+|,|:|;",
                               r["title"] or "")
        for canon in r["drugs"]:
            spec = cfg.BY_CANONICAL[canon]
            alias = alias_as_written(canon, r["title"], r["abstract"])
            # Regimen is inferred from the title only - titles state the regimen, whereas
            # abstracts name many drugs in passing. Clauses naming *this* compound are
            # excluded so the row's own agent is not counted as its own partner.
            track, partner_target = cfg.classify_combination(
                [p for p in title_parts if not cfg.ALIAS_REGEX[canon].search(p)])
            is_mono = track == "monotherapy"
            for bm in r["biomarkers"]:
                btype, bscope = biomarker_fields(bm)
                add(source_type=source_type,
                    citation=(f"{r['first_author'] or 'authors not parsed'} "
                              f"({r['year'] or 'year not parsed'}). {r['title']}"
                              + (f" {r['journal']}." if r["journal"] else ""))[:900],
                    url_or_doi=(f"https://doi.org/{r['doi']}" if r["doi"] else r["url"]),
                    dataset_id=dataset_id,
                    year=year,
                    target=spec["target"],
                    target_family=TARGET_FAMILY[spec["target"]],
                    compound=canon,
                    alias=alias,
                    dose=None, schedule=None,
                    combination_track=track,
                    combo_partner=None,
                    combo_partner_target=partner_target,
                    is_monotherapy=is_mono,
                    indication=indication,
                    indication_category=categorize_indication(indication),
                    histology=None,
                    treatment_setting=setting,
                    prior_therapies=None,
                    model_type=model_type,
                    model_id=None,
                    n=None,
                    population_description=None,
                    perturbation_type="chemical",
                    specimen_type=None,
                    specimen_timing="not_reported",
                    biomarker_name=bm,
                    biomarker_type=btype,
                    biomarker_scope=bscope,
                    assay=None, assay_modality=None, cutoff=None, biomarker_status=None,
                    response_metric="not_reported",
                    response_value=None,
                    units=None,
                    endpoint_class=None,
                    direction=None,
                    effect_size=None, effect_size_type=None, p_value=None, q_value=None,
                    ci_low=None, ci_high=None,
                    evidence_tier=tier,
                    reproducibility=None,
                    predictive_vs_prognostic="unclear",
                    evidence_basis=("single_arm_association" if model_type == "patient"
                                    else "preclinical_correlation"),
                    target_specific_vs_combo=attribution_for(canon, is_mono),
                    baseline_vs_pd=("pharmacodynamic" if is_pd_marker(bm) else "baseline"),
                    notes=(
                        "UNCURATED KEYWORD CO-MENTION: compound and biomarker were both matched "
                        "by regular expression in the title/abstract/MeSH of this record. No "
                        "association is asserted - nobody has read the paper, no effect size or "
                        "p-value was extracted, direction unknown. Must be curated by a human "
                        "before use. "
                        f"evidence_tier and model_type assigned by text classification "
                        f"('{label or 'unclassified'}'); combination_track inferred from the "
                        f"title only. Retrieval: {r['source_note']}."
                        + (" Record also describes a genetic (CRISPR/RNAi) perturbation; "
                           "perturbation_type is 'chemical' because the row matched a compound."
                           if GENETIC_RX.search((r["title"] or "") + (r["abstract"] or "")) else "")
                    )[:1900])
                n += 1
    STATS["literature"] = n
    log(f"      {n} literature rows from {len(lit)} records "
        f"({skipped_off_topic} dropped: no oncology context; "
        f"{skipped_no_bm} dropped: no controlled-vocabulary biomarker detected)")


# ===========================================================================
# validation + write
# ===========================================================================
def write_json_list(path: Path, rows: list[dict]) -> None:
    """Write a JSON list with exactly one object per line.

    The result is an ordinary JSON array - ``json.load`` reads it identically - but the
    one-object-per-line layout also lets ``backend/ingest.py`` stream it a row at a time
    instead of materialising a ~70 MB parse tree, which matters on a small container.
    """
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("[\n")
        for i, row in enumerate(rows):
            fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False))
            fh.write(",\n" if i < len(rows) - 1 else "\n")
        fh.write("]\n")


REQUIRED_ALWAYS_PRESENT = {"source_type", "citation", "target", "compound", "indication",
                           "model_type", "biomarker_name", "biomarker_type", "response_metric"}


def validate(rows: list[dict], model, label: str) -> list[dict]:
    """Validate every row against the real SQLModel class, then return a compact copy.

    Two passes, because both properties matter:

      1. Each row must carry *exactly* the model's field set (minus the autoincrement
         ``id``). This catches a builder that silently forgets a column.
      2. The compact copy - the same row with explicit nulls dropped - must still
         construct and must round-trip to an identical field-by-field object. Dropping
         nulls roughly halves the on-disk size without changing what loads, because every
         omitted field is Optional with a ``None`` default.

    Fails loudly on the first offender rather than writing a bad file.
    """
    log(f"\n[validate] {len(rows)} {label} rows against the SQLModel schema ...")
    expected = set(model.model_fields) - {"id"}
    compact: list[dict] = []
    for i, row in enumerate(rows):
        keys = set(row)
        if keys != expected:
            raise AssertionError(
                f"{label} row {i}: key set does not match {model.__name__}. "
                f"unexpected={sorted(keys - expected)} missing={sorted(expected - keys)}")
        try:
            full = model(**row)
        except Exception as e:  # noqa: BLE001
            raise AssertionError(f"{label} row {i} failed {model.__name__}(**row): {e}\n{row}")
        for field, allowed in VOCAB_FIELDS.items():
            if field not in row:
                continue
            value = row[field]
            if value is not None and value not in allowed:
                raise AssertionError(
                    f"{label} row {i}: {field}={value!r} is not in backend/vocabulary.py "
                    f"({sorted(allowed)}). The API validates filters against that list, so "
                    f"this row would be unreachable in the UI.")
        thin = {k: v for k, v in row.items() if v is not None}
        missing_required = REQUIRED_ALWAYS_PRESENT & expected - set(thin)
        if missing_required:
            raise AssertionError(
                f"{label} row {i}: required field(s) {sorted(missing_required)} are null")
        try:
            rebuilt = model(**thin)
        except Exception as e:  # noqa: BLE001
            raise AssertionError(f"{label} row {i} failed to rebuild from the compact form: {e}")
        for f in expected:
            if getattr(full, f) != getattr(rebuilt, f):
                raise AssertionError(
                    f"{label} row {i}: field {f!r} differs after dropping nulls "
                    f"({getattr(full, f)!r} vs {getattr(rebuilt, f)!r})")
        compact.append(thin)
    log(f"      all {len(rows)} rows carry the exact {model.__name__} field set "
        f"({len(expected)} keys) and construct cleanly as {model.__name__}(**row)")
    log(f"      compact form (explicit nulls dropped) round-trips identically for all rows")
    return compact


def main() -> None:
    path = DATA / "ddr_harvest.json"
    harvest = json.loads(path.read_text(encoding="utf-8"))
    log(f"loaded {path.name}: " + ", ".join(f"{k}={len(v)}" for k, v in harvest.items()))

    ctgov = harvest.get("ctgov", [])
    meas = harvest.get("gdsc", [])
    lit = harvest.get("literature", [])

    compounds = build_compounds(ctgov)
    if ctgov:
        build_registry(ctgov)
    if meas:
        build_gdsc_measurements(meas)
        build_gdsc_lineage(meas)
        build_gdsc_mutation(meas)
    if lit:
        build_literature(lit)

    compounds_out = validate(compounds, Compound, "compound")
    evidence_out = validate(ROWS, Evidence, "evidence")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ddr_compounds.json").write_text(
        json.dumps(compounds_out, indent=1, ensure_ascii=False), encoding="utf-8")
    write_json_list(OUT_DIR / "ddr_evidence.json", evidence_out)
    # Prove the file we just wrote is an ordinary JSON list that parses back identically.
    reloaded = json.loads((OUT_DIR / "ddr_evidence.json").read_text(encoding="utf-8"))
    if reloaded != evidence_out:
        raise AssertionError("ddr_evidence.json did not round-trip through json.loads")
    log(f"      ddr_evidence.json re-parses with json.loads() into an identical "
        f"{len(reloaded)}-element list")

    log(f"\nwrote {OUT_DIR / 'ddr_compounds.json'} ({len(compounds_out)} rows, "
        f"{(OUT_DIR / 'ddr_compounds.json').stat().st_size / 1e3:.0f} KB)")
    log(f"wrote {OUT_DIR / 'ddr_evidence.json'} ({len(evidence_out)} rows, "
        f"{(OUT_DIR / 'ddr_evidence.json').stat().st_size / 1e6:.1f} MB)")
    log("\nrow-type counts:")
    for k, v in sorted(STATS.items()):
        if not k.startswith("_"):
            log(f"   {v:8d}  {k}")
    log(f"\n   driver-gene hypothesis panel size: {STATS['_panel']}")


if __name__ == "__main__":
    main()
