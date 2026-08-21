"""
Analytics layer: turns raw evidence rows into the aggregated views the DDR
program needs (biomarker ranking, indication x compound/target landscape,
evidence composition, volcano-style effect/significance scatter, per-target
rollups).

All functions take a list of Evidence rows (already filtered by the caller) so
insights can be scoped to any subset of the matrix - one target, one
combination track, one indication category, and so on.

Scoring philosophy
------------------
Every score in this module is a *transparent heuristic*, not a validated
model. The program brief distinguishes hypothesis-generating signals from
validated ones, so each biomarker is scored on eight named dimensions that are
returned individually alongside the composite. A reviewer can therefore see
*why* a biomarker ranked where it did and disagree with a specific dimension
rather than with an opaque number. Weights live in ``SCORE_WEIGHTS`` so they
are easy to re-tune without touching the maths.

Limitations that apply to every score here:

  * Sub-scores are bounded to 0-1 by saturating transforms, so a biomarker with
    50 supporting rows is not ranked 5x above one with 10.
  * Absence of data scores 0, not "unknown". A biomarker only ever tested in
    one perturbation modality genuinely cannot demonstrate concordance, but a
    0 should be read as "not shown" rather than "shown to be false".
  * ``prevalence`` is a *coverage* proxy, not real population prevalence.
"""

import math
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional

from models import Evidence

# ---------------------------------------------------------------------------
# Row contract
# ---------------------------------------------------------------------------
# Every Evidence attribute this module reads. The functions below only ever use
# attribute access, so a caller may pass full Evidence objects *or* any row that
# exposes these names - which lets main.py select just these columns instead of
# hydrating 50k+ ORM instances per request (a ~10x latency difference on the
# unscoped matrix).
#
# Keeping the list here rather than in main.py means the module that does the
# reading owns the contract. tests/test_insights_contract.py fails if an insight
# starts reading a field that is not listed, so the two cannot drift apart.
INSIGHT_FIELDS = (
    "assay_modality",
    "biomarker_name",
    "biomarker_scope",
    "biomarker_type",
    "combination_track",
    "compound",
    "dataset_id",
    "direction",
    "effect_size",
    "evidence_basis",
    "evidence_tier",
    "id",
    "indication",
    "indication_category",
    "is_monotherapy",
    "model_type",
    "n",
    "p_value",
    "perturbation_type",
    "predictive_vs_prognostic",
    "reproducibility",
    "source_type",
    "specimen_timing",
    "specimen_type",
    "target",
    "target_family",
    "target_specific_vs_combo",
)

# ---------------------------------------------------------------------------
# Weight constants (tune these, not the formulas)
# ---------------------------------------------------------------------------

# Evidence tiers ranked so clinical > in-vivo > in-vitro.
TIER_WEIGHT = {"clinical": 1.0, "preclinical_invivo": 0.6, "preclinical_invitro": 0.35}

# Reproducibility as recorded on the row itself.
REPRO_WEIGHT = {"reproducible": 1.0, "multi_dataset": 0.65, "single_dataset": 0.3}

# Source quality. `internal_aprea` is gone (no confidential tier any more);
# `registry` (ClinicalTrials.gov and similar) and `preprint` were added.
SOURCE_WEIGHT = {
    "peer_reviewed": 1.0,
    "database": 0.85,
    "registry": 0.7,
    "preprint": 0.55,
    "abstract": 0.5,
    "patent": 0.4,
}

# Study design, per the brief's hierarchy. Only `randomized_interaction`
# supports a genuine claim of predictiveness (a biomarker x treatment
# interaction term); everything below it is association or selection-biased.
BASIS_WEIGHT = {
    "randomized_interaction": 1.0,
    "single_arm_association": 0.6,
    "responder_only": 0.35,
    "preclinical_correlation": 0.15,
}

# How tractable the measurement is in a real clinical workflow. NGS / IHC /
# bulk RNA / ctDNA are routine in oncology diagnostics; proteomics and
# functional assays (e.g. ex-vivo drug sensitivity) are research-grade.
ASSAY_WEIGHT = {
    "ngs": 1.0,
    "ihc": 0.95,
    "liquid_biopsy": 0.85,
    "rna": 0.8,
    "proteomics": 0.45,
    "functional": 0.3,
}

# Biomarker classes, by how standardised their reporting is.
BIOMARKER_TYPE_WEIGHT = {
    "mutation": 1.0,
    "cnv": 0.95,
    "fusion": 0.9,
    "expression": 0.7,
    "protein": 0.65,
    "phospho": 0.45,
    "signature": 0.4,
}

# Specimen availability for a retrospective validation study.
SPECIMEN_WEIGHT = {
    "tumor_tissue": 1.0,
    "plasma_ctdna": 0.9,
    "whole_blood": 0.6,
    "pbmc": 0.5,
    "cell_pellet": 0.35,
    "skin_biopsy": 0.3,
    "n/a": 0.1,
}

# Baseline specimens can select patients prospectively; on-treatment specimens
# only support pharmacodynamic claims.
TIMING_WEIGHT = {
    "baseline": 1.0,
    "on_treatment": 0.55,
    "progression": 0.45,
    "not_reported": 0.2,
}

# Curated replication-stress / DDR-dependency feature set. A biomarker whose
# name mentions one of these is mechanistically connected to the pathway the
# DDR agents act on, rather than being a generic prognostic marker. Matching is
# a case-insensitive substring test on `biomarker_name`, which is deliberately
# permissive ("CCNE1 amplification", "Cyclin E1 high" and "CCNE1/CDK2 activity"
# all match) and therefore can over-match; it is a prior, not a proof.
REPLICATION_STRESS_FEATURES = [
    "ccne1", "cyclin e",
    "myc",
    "replication stress",
    "tp53", "p53",
    "rb1", "e2f",
    "fbxw7",
    "ppp2r1a",
    "slfn11",
    "atr", "atm",
    "chk1", "chek1",
    "pkmyt1",
    "cdk1", "cdk2",
    "gammah2ax", "yh2ax", "h2ax",
    "pcdk1",
]

# Composite weights for the eight dimensions. Must sum to 1.0; the composite
# is a plain weighted mean so a dimension's weight is exactly its share of the
# final score. Ordered by how decision-relevant the brief treats each one.
SCORE_WEIGHTS = {
    "clinical_evidence": 0.20,
    "reproducibility": 0.15,
    "chemical_genetic_concordance": 0.15,
    "mechanistic_link": 0.12,
    "attribution": 0.12,
    "assay_feasibility": 0.09,
    "validation_feasibility": 0.09,
    "prevalence": 0.08,
}

SCORE_DIMENSIONS = list(SCORE_WEIGHTS)


# ---------------------------------------------------------------------------
# Small numeric helpers (all empty-safe - an empty database must not 500)
# ---------------------------------------------------------------------------


def _mean(xs: Iterable[Optional[float]]) -> float:
    """Mean of the non-null values, or 0.0 when there are none."""
    vals = [x for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _share(rows: List[Evidence], predicate) -> float:
    """Fraction of rows satisfying `predicate`; 0.0 for an empty list."""
    if not rows:
        return 0.0
    return sum(1 for r in rows if predicate(r)) / len(rows)


def _saturate(value: float, full: float) -> float:
    """Diminishing-returns transform: 0 at value=0, ~1 once value reaches `full`.

    Used so support counts (studies, datasets, indications) contribute on a
    bounded 0-1 scale instead of letting one heavily-studied biomarker dominate.
    """
    if value <= 0 or full <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(full))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _consensus_direction(rows: List[Evidence]) -> Optional[str]:
    """Majority `direction` call among rows that made one; None if none did."""
    calls = Counter(r.direction for r in rows if r.direction in ("sensitive", "resistant"))
    if not calls:
        return None
    return calls.most_common(1)[0][0]


def _count_by(rows: List[Evidence], attr: str) -> List[dict]:
    counts: Dict[str, int] = defaultdict(int)
    for r in rows:
        counts[getattr(r, attr) or "unknown"] += 1
    return [{"key": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]


def _pct(rows: List[Evidence], predicate) -> float:
    return round(100 * _share(rows, predicate), 1)


# ---------------------------------------------------------------------------
# Headline counts
# ---------------------------------------------------------------------------


def summary(rows: List[Evidence]) -> dict:
    """Headline counts for the dashboard cards.

    `n_trials` counts distinct `dataset_id`s that look like ClinicalTrials.gov
    identifiers (prefix "NCT"), which is how registry-sourced clinical evidence
    is keyed in this schema.
    """
    return {
        "total_entries": len(rows),
        "n_targets": len({r.target for r in rows if r.target}),
        "n_biomarkers": len({r.biomarker_name for r in rows if r.biomarker_name}),
        "n_compounds": len({r.compound for r in rows if r.compound}),
        "n_indications": len({r.indication for r in rows if r.indication}),
        "n_clinical": sum(1 for r in rows if r.evidence_tier == "clinical"),
        "n_preclinical": sum(
            1 for r in rows if r.evidence_tier in ("preclinical_invitro", "preclinical_invivo")
        ),
        "n_trials": len(
            {
                r.dataset_id
                for r in rows
                if r.dataset_id and r.dataset_id.upper().startswith("NCT")
            }
        ),
        "n_sensitive": sum(1 for r in rows if r.direction == "sensitive"),
        "n_resistant": sum(1 for r in rows if r.direction == "resistant"),
        "pct_predictive": _pct(rows, lambda r: r.predictive_vs_prognostic == "predictive"),
        "pct_randomized_interaction": _pct(
            rows, lambda r: r.evidence_basis == "randomized_interaction"
        ),
    }


def composition(rows: List[Evidence]) -> dict:
    """Breakdowns used for the pie/bar charts."""
    return {
        "by_source_type": _count_by(rows, "source_type"),
        "by_model_type": _count_by(rows, "model_type"),
        "by_evidence_tier": _count_by(rows, "evidence_tier"),
        "by_biomarker_type": _count_by(rows, "biomarker_type"),
        "by_target": _count_by(rows, "target"),
        "by_combination_track": _count_by(rows, "combination_track"),
        "by_indication_category": _count_by(rows, "indication_category"),
        "by_perturbation_type": _count_by(rows, "perturbation_type"),
    }


# ---------------------------------------------------------------------------
# The eight biomarker scoring dimensions
#
# Each takes the rows supporting one biomarker and returns a 0-1 score. They
# are separate functions so each one can be read, criticised and replaced
# independently.
# ---------------------------------------------------------------------------


def _score_clinical_evidence(grp: List[Evidence]) -> float:
    """Strength of *human* evidence.

    Blend of three signals: the recorded evidence tier, the share of rows in
    actual patients (`model_type == "patient"`), and study design via
    `evidence_basis`. Limitation: a large single-arm trial and a small one score
    the same - sample size is handled in `validation_feasibility` instead.
    """
    tier = _mean([TIER_WEIGHT.get(r.evidence_tier, 0.35) for r in grp])
    patient_share = _share(grp, lambda r: r.model_type == "patient")
    basis = _mean([BASIS_WEIGHT.get(r.evidence_basis, 0.15) for r in grp])
    return _clamp01(0.40 * tier + 0.30 * patient_share + 0.30 * basis)


def _score_reproducibility(grp: List[Evidence], n_datasets: int) -> float:
    """Has the signal been seen more than once, in more than one place?

    Combines the curated `reproducibility` field with the number of DISTINCT
    `dataset_id`s supporting the biomarker. Rows with no `dataset_id` cannot
    contribute to the dataset count, so poorly-provenanced evidence is
    penalised - which is intended.
    """
    recorded = _mean([REPRO_WEIGHT.get(r.reproducibility, 0.3) for r in grp])
    breadth = _saturate(n_datasets, 5)  # 5 independent datasets ~ full marks
    return _clamp01(0.6 * recorded + 0.4 * breadth)


def _score_chemical_genetic_concordance(grp: List[Evidence]) -> float:
    """Does chemical inhibition agree with genetic loss of the same target?

    This is the brief's "real target biology vs compound off-target effect"
    test. Scored 0 when only one `perturbation_type` is present, because a
    single modality cannot demonstrate concordance at all. When both are
    present, the majority `direction` call within each modality is compared:

        agree                        -> 1.0
        both present, one has no call -> 0.5
        disagree                      -> 0.25 (not 0: the target was probed
                                        both ways, the discordance is itself
                                        an informative finding)
    """
    chemical = [r for r in grp if r.perturbation_type == "chemical"]
    genetic = [r for r in grp if r.perturbation_type == "genetic"]
    if not chemical or not genetic:
        return 0.0
    chem_dir = _consensus_direction(chemical)
    gen_dir = _consensus_direction(genetic)
    if chem_dir is None or gen_dir is None:
        return 0.5
    return 1.0 if chem_dir == gen_dir else 0.25


def _is_replication_stress_feature(biomarker_name: str) -> bool:
    name = (biomarker_name or "").lower()
    return any(token in name for token in REPLICATION_STRESS_FEATURES)


def _score_mechanistic_link(grp: List[Evidence], biomarker_name: str) -> float:
    """Plausible mechanistic connection to replication stress / DDR dependency.

    Two equally-weighted parts: (a) the share of supporting rows attributed to
    the DDR agent itself (`target_specific_vs_combo == "target_specific"`), and
    (b) whether the biomarker matches the curated `REPLICATION_STRESS_FEATURES`
    set. Limitation: (b) is a hand-maintained substring list, so a genuinely
    novel mechanistic biomarker scores only half marks until it is added.
    """
    specific = _share(grp, lambda r: r.target_specific_vs_combo == "target_specific")
    curated = 1.0 if _is_replication_stress_feature(biomarker_name) else 0.0
    return _clamp01(0.5 * specific + 0.5 * curated)


def _score_prevalence(n_indications: int, n_categories: int) -> float:
    """Breadth of tumour types the biomarker has evidence in.

    IMPORTANT: this is a *coverage proxy*, NOT true population prevalence. It
    measures how many distinct `indication`s and `indication_category`s the
    literature has tested the biomarker in, which correlates with commercial
    breadth only loosely. Real prevalence requires per-indication alteration
    frequencies from GDC / cBioPortal / TCGA, which this schema does not hold.
    A biomarker studied only in ovarian cancer scores low here even if it is
    highly prevalent there.
    """
    return _clamp01(0.6 * _saturate(n_indications, 6) + 0.4 * _saturate(n_categories, 4))


def _score_attribution(grp: List[Evidence]) -> float:
    """Can the signal be attributed to the DDR agent, not its partner?

    Share of supporting rows that are either monotherapy (nothing else to
    attribute the effect to) or explicitly curated as `target_specific`.
    Limitation: monotherapy evidence is treated as fully attributable, which
    ignores the possibility that the biomarker is purely prognostic.
    """
    return _share(
        grp,
        lambda r: bool(r.is_monotherapy) or r.target_specific_vs_combo == "target_specific",
    )


def _score_assay_feasibility(grp: List[Evidence]) -> float:
    """How easily the biomarker could be measured in a clinical assay.

    From `assay_modality` (NGS / IHC / RNA / ctDNA are routine diagnostics;
    proteomics and functional assays are research-grade) plus `biomarker_type`
    (mutations and copy number are reported to a standard; signatures and
    phospho-markers need bespoke, harder-to-standardise assays). Limitation:
    ignores whether a validated, regulator-ready kit actually exists.
    """
    modality = _mean([ASSAY_WEIGHT.get(r.assay_modality, 0.4) for r in grp])
    btype = _mean([BIOMARKER_TYPE_WEIGHT.get(r.biomarker_type, 0.5) for r in grp])
    return _clamp01(0.7 * modality + 0.3 * btype)


def _score_validation_feasibility(grp: List[Evidence]) -> float:
    """Could this be validated retrospectively on existing specimens?

    From `specimen_type` and `specimen_timing` (baseline tumour tissue or
    plasma ctDNA is the feasible case) plus total supporting n across the rows,
    since a validation study needs biomarker-positive patients to exist.
    Limitation: total n sums independent cohorts of very different kinds
    (cell lines and patients), so treat it as an order-of-magnitude signal.
    """
    specimen = _mean([SPECIMEN_WEIGHT.get(r.specimen_type, 0.3) for r in grp])
    timing = _mean([TIMING_WEIGHT.get(r.specimen_timing, 0.2) for r in grp])
    total_n = sum(r.n for r in grp if r.n)
    support = _saturate(total_n, 300)
    return _clamp01(0.4 * specimen + 0.3 * timing + 0.3 * support)


def biomarker_ranking(rows: List[Evidence]) -> List[dict]:
    """Rank candidate biomarkers over the brief's eight evaluation dimensions.

        composite_score = sum(SCORE_WEIGHTS[d] * sub_score[d] for d in dims)

    Each sub-score is normalised to 0-1 and returned individually so the UI can
    show the breakdown and a reviewer can audit the ranking. The weights live
    in ``SCORE_WEIGHTS``.

    The dimensions are:

      1. `clinical_evidence`             - strength of human clinical evidence
      2. `reproducibility`               - repeated across independent datasets
      3. `chemical_genetic_concordance`  - drug and CRISPR/RNAi agree
      4. `mechanistic_link`              - tied to replication stress biology
      5. `attribution`                   - DDR agent vs combination partner
      6. `assay_feasibility`             - measurable in a clinical assay
      7. `validation_feasibility`        - validatable on available specimens
      8. `prevalence`                    - breadth of tumour types (a coverage
                                           proxy, not real prevalence)

    This is a hypothesis-generating ranking. A high composite means "worth
    chasing", not "validated"; only rows with
    `evidence_basis == "randomized_interaction"` support a genuine claim that a
    biomarker is predictive rather than prognostic.
    """
    groups: Dict[str, List[Evidence]] = defaultdict(list)
    for r in rows:
        groups[r.biomarker_name].append(r)

    out = []
    for name, grp in groups.items():
        n_studies = len(grp)
        datasets = {r.dataset_id for r in grp if r.dataset_id}
        indications = {r.indication for r in grp if r.indication}
        categories = {r.indication_category for r in grp if r.indication_category}
        targets = sorted({r.target for r in grp if r.target})

        sub_scores = {
            "clinical_evidence": _score_clinical_evidence(grp),
            "reproducibility": _score_reproducibility(grp, len(datasets)),
            "chemical_genetic_concordance": _score_chemical_genetic_concordance(grp),
            "mechanistic_link": _score_mechanistic_link(grp, name),
            "attribution": _score_attribution(grp),
            "assay_feasibility": _score_assay_feasibility(grp),
            "validation_feasibility": _score_validation_feasibility(grp),
            "prevalence": _score_prevalence(len(indications), len(categories)),
        }
        composite = sum(SCORE_WEIGHTS[dim] * sub_scores[dim] for dim in SCORE_WEIGHTS)

        entry = {
            "biomarker_name": name,
            "biomarker_type": grp[0].biomarker_type,
            "biomarker_scope": next((r.biomarker_scope for r in grp if r.biomarker_scope), None),
            "n_studies": n_studies,
            "n_datasets": len(datasets),
            "targets": targets,
            "frac_sensitive": round(_share(grp, lambda r: r.direction == "sensitive"), 2),
            "mean_abs_effect": round(
                _mean([abs(r.effect_size) for r in grp if r.effect_size is not None]), 3
            ),
            "pct_clinical": _pct(grp, lambda r: r.evidence_tier == "clinical"),
            "pct_predictive": _pct(grp, lambda r: r.predictive_vs_prognostic == "predictive"),
            "composite_score": round(composite, 4),
        }
        entry.update({dim: round(score, 3) for dim, score in sub_scores.items()})
        out.append(entry)

    return sorted(out, key=lambda d: (-d["composite_score"], d["biomarker_name"]))


# ---------------------------------------------------------------------------
# Landscape / scatter / rollups
# ---------------------------------------------------------------------------

LANDSCAPE_MODES = {"compound": "compound", "target": "target"}


def indication_landscape(rows: List[Evidence], by: str = "compound") -> dict:
    """Indication x (compound | target) grid for the landscape heatmap.

    `by="compound"` gives the original drug-level view; `by="target"` collapses
    every agent onto its DDR target, which is the readable view now that the
    matrix spans many targets. Cell value = share of `sensitive` observations
    plus the number of supporting rows. Empty (indication, column) pairs are
    omitted rather than emitted as zeros, so the payload stays sparse.

    Returns `{mode, rows, columns, cells}` where `rows` are indications and
    `columns` are the values of the chosen grouping attribute.
    """
    column_attr = LANDSCAPE_MODES.get(by, "compound")
    mode = "target" if column_attr == "target" else "compound"

    grid: Dict[str, Dict[str, List[Evidence]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        column = getattr(r, column_attr) or "unknown"
        grid[r.indication or "unknown"][column].append(r)

    cells = []
    for indication in sorted(grid):
        for column in sorted(grid[indication]):
            grp = grid[indication][column]
            cells.append(
                {
                    "row": indication,
                    "column": column,
                    "indication": indication,
                    mode: column,
                    "n": len(grp),
                    "frac_sensitive": round(_share(grp, lambda r: r.direction == "sensitive"), 2),
                    "mean_abs_effect": round(
                        _mean([abs(r.effect_size) for r in grp if r.effect_size is not None]), 3
                    ),
                    "n_clinical": sum(1 for r in grp if r.evidence_tier == "clinical"),
                }
            )

    return {
        "mode": mode,
        "rows": sorted(grid),
        "columns": sorted({c["column"] for c in cells}),
        "cells": cells,
    }


def volcano(rows: List[Evidence]) -> List[dict]:
    """Points for an effect-size vs -log10(p) scatter.

    Only rows with BOTH an effect size and a p-value can be plotted, which
    excludes much of the real corpus (curated clinical rows often report
    neither). `target`, `combination_track` and `perturbation_type` are
    included so the scatter can be coloured or faceted by them.
    """
    pts = []
    for r in rows:
        if r.effect_size is None or r.p_value is None:
            continue
        pts.append(
            {
                "id": r.id,
                "biomarker_name": r.biomarker_name,
                "target": r.target,
                "compound": r.compound,
                "indication": r.indication,
                "combination_track": r.combination_track,
                "perturbation_type": r.perturbation_type,
                "effect_size": r.effect_size,
                "neg_log10_p": round(-math.log10(max(r.p_value, 1e-6)), 3),
                "direction": r.direction,
                "n": r.n,
                "evidence_tier": r.evidence_tier,
            }
        )
    return pts


def target_overview(rows: List[Evidence]) -> List[dict]:
    """Per-DDR-target rollup for the target panel.

    One entry per `target` present in the supplied rows, sorted by row count
    descending. `top_biomarkers` is the three biomarkers with the most
    supporting rows for that target - a volume measure, deliberately NOT the
    ranking score, so this panel shows "what has been studied" while
    `biomarker_ranking` shows "what looks promising".
    """
    groups: Dict[str, List[Evidence]] = defaultdict(list)
    for r in rows:
        groups[r.target or "unknown"].append(r)

    out = []
    for target, grp in groups.items():
        counts = Counter(r.biomarker_name for r in grp if r.biomarker_name)
        out.append(
            {
                "target": target,
                "target_family": next((r.target_family for r in grp if r.target_family), None),
                "n_rows": len(grp),
                "n_compounds": len({r.compound for r in grp if r.compound}),
                "n_biomarkers": len(counts),
                "n_indications": len({r.indication for r in grp if r.indication}),
                "n_clinical": sum(1 for r in grp if r.evidence_tier == "clinical"),
                "frac_sensitive": round(_share(grp, lambda r: r.direction == "sensitive"), 2),
                "top_biomarkers": [
                    {"biomarker_name": name, "n": n}
                    for name, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:3]
                ],
            }
        )
    return sorted(out, key=lambda d: (-d["n_rows"], d["target"]))
