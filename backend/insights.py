"""
Analytics layer: turns the raw evidence rows into the aggregated views Julie
wants (biomarker ranking, indication x regimen landscape, evidence composition,
volcano-style effect/significance scatter).

All functions take a list of Evidence rows (already filtered by the caller) so
insights can be scoped to any subset of the matrix.
"""

import math
from collections import defaultdict
from typing import Dict, List

from models import Evidence

# Evidence tiers ranked so clinical > in-vivo > in-vitro.
TIER_WEIGHT = {"clinical": 1.0, "preclinical_invivo": 0.6, "preclinical_invitro": 0.35}
REPRO_WEIGHT = {"reproducible": 1.0, "multi_dataset": 0.65, "single_dataset": 0.3}
SOURCE_WEIGHT = {
    "peer_reviewed": 1.0,
    "database": 0.85,
    "internal_aprea": 0.8,
    "abstract": 0.5,
    "patent": 0.4,
}


def _mean(xs: List[float]) -> float:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def summary(rows: List[Evidence]) -> dict:
    """Headline counts for the dashboard cards."""
    return {
        "total_entries": len(rows),
        "n_biomarkers": len({r.biomarker_name for r in rows}),
        "n_compounds": len({r.compound for r in rows}),
        "n_indications": len({r.indication for r in rows}),
        "n_clinical": sum(1 for r in rows if r.evidence_tier == "clinical"),
        "n_confidential": sum(1 for r in rows if r.is_aprea_confidential),
        "n_sensitive": sum(1 for r in rows if r.direction == "sensitive"),
        "n_resistant": sum(1 for r in rows if r.direction == "resistant"),
        "pct_predictive": round(
            100 * _mean([1.0 if r.predictive_vs_prognostic == "predictive" else 0.0 for r in rows]), 1
        ),
    }


def _count_by(rows: List[Evidence], attr: str) -> List[dict]:
    counts: Dict[str, int] = defaultdict(int)
    for r in rows:
        counts[getattr(r, attr) or "unknown"] += 1
    return [{"key": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


def composition(rows: List[Evidence]) -> dict:
    """Breakdowns used for pie/bar charts."""
    return {
        "by_source_type": _count_by(rows, "source_type"),
        "by_model_type": _count_by(rows, "model_type"),
        "by_evidence_tier": _count_by(rows, "evidence_tier"),
        "by_biomarker_type": _count_by(rows, "biomarker_type"),
    }


def biomarker_ranking(rows: List[Evidence]) -> List[dict]:
    """
    Rank candidate biomarkers by a composite evidence score:

        score = mean(|effect|) x reproducibility x evidence-tier x source-quality
                x directional-consistency x log-support(n_studies)

    This is a transparent, tweakable heuristic - the point is to demonstrate the
    ranking output, not to assert a validated scoring model.
    """
    groups: Dict[str, List[Evidence]] = defaultdict(list)
    for r in rows:
        groups[r.biomarker_name].append(r)

    out = []
    for name, grp in groups.items():
        n_studies = len(grp)
        n_sensitive = sum(1 for r in grp if r.direction == "sensitive")
        # directional consistency: how one-sided is the sensitive/resistant split
        frac_sensitive = n_sensitive / n_studies if n_studies else 0
        consistency = abs(2 * frac_sensitive - 1)  # 0 (mixed) .. 1 (unanimous)

        mean_abs_effect = _mean([abs(r.effect_size) for r in grp if r.effect_size is not None])
        repro = _mean([REPRO_WEIGHT.get(r.reproducibility, 0.3) for r in grp])
        tier = _mean([TIER_WEIGHT.get(r.evidence_tier, 0.35) for r in grp])
        source = _mean([SOURCE_WEIGHT.get(r.source_type, 0.5) for r in grp])
        support = math.log1p(n_studies) / math.log1p(30)  # saturating support factor

        score = mean_abs_effect * repro * tier * source * (0.4 + 0.6 * consistency) * (0.5 + 0.5 * support)

        out.append(
            {
                "biomarker_name": name,
                "biomarker_type": grp[0].biomarker_type,
                "n_studies": n_studies,
                "frac_sensitive": round(frac_sensitive, 2),
                "mean_abs_effect": round(mean_abs_effect, 3),
                "reproducibility_score": round(repro, 2),
                "tier_score": round(tier, 2),
                "pct_predictive": round(
                    100 * _mean([1.0 if r.predictive_vs_prognostic == "predictive" else 0.0 for r in grp]), 1
                ),
                "pct_clinical": round(
                    100 * _mean([1.0 if r.evidence_tier == "clinical" else 0.0 for r in grp]), 1
                ),
                "composite_score": round(score, 4),
            }
        )
    return sorted(out, key=lambda d: -d["composite_score"])


def indication_landscape(rows: List[Evidence]) -> dict:
    """
    Indication x compound grid: cell value = share of 'sensitive' observations
    plus the number of supporting rows. Feeds the landscape heatmap/table.
    """
    grid: Dict[str, Dict[str, List[Evidence]]] = defaultdict(lambda: defaultdict(list))
    indications, compounds = set(), set()
    for r in rows:
        grid[r.indication][r.compound].append(r)
        indications.add(r.indication)
        compounds.add(r.compound)

    cells = []
    for ind in indications:
        for comp in compounds:
            grp = grid[ind][comp]
            if not grp:
                continue
            n_sens = sum(1 for r in grp if r.direction == "sensitive")
            cells.append(
                {
                    "indication": ind,
                    "compound": comp,
                    "n": len(grp),
                    "frac_sensitive": round(n_sens / len(grp), 2),
                    "mean_abs_effect": round(_mean([abs(r.effect_size) for r in grp if r.effect_size]), 3),
                }
            )
    return {
        "indications": sorted(indications),
        "compounds": sorted(compounds),
        "cells": cells,
    }


def volcano(rows: List[Evidence]) -> List[dict]:
    """Points for an effect-size vs -log10(p) scatter, colored by direction."""
    pts = []
    for r in rows:
        if r.effect_size is None or r.p_value is None:
            continue
        pts.append(
            {
                "id": r.id,
                "biomarker_name": r.biomarker_name,
                "compound": r.compound,
                "indication": r.indication,
                "effect_size": r.effect_size,
                "neg_log10_p": round(-math.log10(max(r.p_value, 1e-6)), 3),
                "direction": r.direction,
                "n": r.n,
                "evidence_tier": r.evidence_tier,
            }
        )
    return pts
