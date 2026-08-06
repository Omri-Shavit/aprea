"""
Deterministic dummy-data generator for the WEE1 evidence matrix.

The data is FAKE but structured to look realistic and to carry plausible
signal (e.g. CCNE1 amplification skews 'sensitive' with large effect sizes),
so the insights dashboard shows meaningful patterns. Seeded RNG => reproducible.

NOTE: none of this is real Aprea data. The rows tagged internal_aprea are
invented placeholders that merely demonstrate the confidential-segregation flag.
"""

import random
from typing import List

from models import Evidence

RNG = random.Random(42)

# --- Controlled vocabularies (also used by the frontend filters) -----------

COMPOUNDS = {
    "adavosertib": ["MK-1775", "AZD1775"],
    "azenosertib": ["ZN-c3"],
    "Debio 0123": [None],
    "IMP7068": [None],
    "APR-WEE1 (Aprea)": [None],  # placeholder for the confidential program
}

INDICATIONS = [
    "High-grade serous ovarian",
    "Uterine serous carcinoma",
    "Triple-negative breast",
    "Small-cell lung",
    "Colorectal",
    "Pancreatic",
    "Head and neck squamous",
    "Osteosarcoma",
    "Acute myeloid leukemia",
    "Melanoma",
]

COMBO_PARTNERS = [
    "gemcitabine",
    "carboplatin",
    "olaparib (PARPi)",
    "irinotecan",
    "paclitaxel",
    "gemcitabine + cisplatin",
]

# Each biomarker carries a "true" profile that shapes the generated rows.
#   p_sensitive : probability a row for this biomarker is 'sensitive'
#   effect      : typical |effect size| when sensitive
#   btype       : biomarker_type
#   pred        : predictive vs prognostic tendency
#   pd          : is this fundamentally a pharmacodynamic marker?
BIOMARKERS = {
    "CCNE1 amplification":      dict(p_sensitive=0.86, effect=0.62, btype="cnv",        pred="predictive",  pd=False),
    "Cyclin E1 high (IHC)":     dict(p_sensitive=0.80, effect=0.55, btype="protein",    pred="predictive",  pd=False),
    "TP53 mutation":            dict(p_sensitive=0.70, effect=0.40, btype="mutation",   pred="predictive",  pd=False),
    "MYC amplification":        dict(p_sensitive=0.68, effect=0.45, btype="cnv",        pred="predictive",  pd=False),
    "BRCA1/2 mutation (HRD)":   dict(p_sensitive=0.66, effect=0.42, btype="mutation",   pred="predictive",  pd=False),
    "SLFN11 high expression":   dict(p_sensitive=0.74, effect=0.50, btype="expression", pred="predictive",  pd=False),
    "Replication-stress signature": dict(p_sensitive=0.72, effect=0.48, btype="signature", pred="predictive", pd=False),
    "KRAS mutation":            dict(p_sensitive=0.54, effect=0.22, btype="mutation",   pred="unclear",     pd=False),
    "FBXW7 mutation":           dict(p_sensitive=0.60, effect=0.30, btype="mutation",   pred="predictive",  pd=False),
    "PPP2R1A mutation":         dict(p_sensitive=0.58, effect=0.28, btype="mutation",   pred="unclear",     pd=False),
    "SETD2 loss":               dict(p_sensitive=0.50, effect=0.18, btype="cnv",        pred="prognostic",  pd=False),
    "p-CDK1 (Tyr15) decrease":  dict(p_sensitive=0.75, effect=0.52, btype="phospho",    pred="unclear",     pd=True),
    "gH2AX increase":           dict(p_sensitive=0.70, effect=0.44, btype="phospho",    pred="unclear",     pd=True),
}

SOURCE_TIERS = {
    "cell_line": "preclinical_invitro",
    "xenograft": "preclinical_invivo",
    "pdx": "preclinical_invivo",
    "patient": "clinical",
}


def _response_for(model_type: str, direction: str):
    """Pick a plausible response metric/value/units for a model type + direction."""
    if model_type == "cell_line":
        metric, units = RNG.choice([("IC50", "nM"), ("AUC", "unitless")])
        if metric == "IC50":
            val = RNG.uniform(30, 400) if direction == "sensitive" else RNG.uniform(600, 5000)
        else:
            val = RNG.uniform(0.15, 0.45) if direction == "sensitive" else RNG.uniform(0.6, 0.95)
    elif model_type in ("xenograft", "pdx"):
        metric, units = "TGI", "%"
        val = RNG.uniform(60, 98) if direction == "sensitive" else RNG.uniform(5, 45)
    else:  # patient
        metric, units = RNG.choice([("ORR", "%"), ("PFS", "months"), ("HR", "unitless")])
        if metric == "ORR":
            val = RNG.uniform(25, 60) if direction == "sensitive" else RNG.uniform(0, 15)
        elif metric == "PFS":
            val = RNG.uniform(6, 14) if direction == "sensitive" else RNG.uniform(1.5, 4)
        else:  # HR (lower is better)
            val = RNG.uniform(0.3, 0.6) if direction == "sensitive" else RNG.uniform(0.9, 1.4)
    return metric, round(val, 3), units


def _effect_stats(profile: dict, direction: str, model_type: str):
    """Effect size + p/q values; stronger & more significant when sensitive."""
    base = profile["effect"] if direction == "sensitive" else profile["effect"] * 0.35
    effect = round(RNG.gauss(base, 0.08), 3)
    est = "pearson_r" if profile["btype"] in ("expression", "signature") else "cohens_d"
    if model_type == "patient":
        est = "hazard_ratio"
        effect = round(RNG.uniform(0.35, 0.7) if direction == "sensitive" else RNG.uniform(0.85, 1.2), 3)
    # bigger effect => smaller p; add noise
    p = max(1e-6, RNG.gauss(0.001 if direction == "sensitive" else 0.2, 0.05))
    p = min(p, 0.9)
    q = min(0.95, p * RNG.uniform(1.5, 8))  # FDR always >= p
    return effect, est, round(p, 5), round(q, 5)


def generate(n_rows: int = 220) -> List[Evidence]:
    rows: List[Evidence] = []
    biomarker_names = list(BIOMARKERS.keys())

    for i in range(n_rows):
        compound = RNG.choice(list(COMPOUNDS.keys()))
        alias = RNG.choice(COMPOUNDS[compound])
        is_aprea = compound.endswith("(Aprea)")

        bm_name = RNG.choice(biomarker_names)
        profile = BIOMARKERS[bm_name]

        model_type = RNG.choices(
            ["cell_line", "xenograft", "pdx", "patient"], weights=[0.5, 0.2, 0.15, 0.15]
        )[0]

        direction = "sensitive" if RNG.random() < profile["p_sensitive"] else "resistant"
        metric, value, units = _response_for(model_type, direction)
        effect, est, p, q = _effect_stats(profile, direction, model_type)

        is_mono = RNG.random() < 0.55
        combo = None if is_mono else RNG.choice(COMBO_PARTNERS)

        # if it's a combination, the WEE1-specific attribution gets murkier
        if is_mono:
            attribution = "wee1_specific"
        else:
            attribution = RNG.choices(
                ["wee1_specific", "combo_driven", "unclear"], weights=[0.3, 0.45, 0.25]
            )[0]

        reproducibility = RNG.choices(
            ["single_dataset", "multi_dataset", "reproducible"],
            weights=[0.45, 0.35, 0.20],
        )[0]

        if profile["pd"]:
            base_vs_pd = "pharmacodynamic"
            pred = "unclear"
        else:
            base_vs_pd = "baseline"
            pred = profile["pred"]

        source_type = (
            "internal_aprea"
            if is_aprea
            else RNG.choices(
                ["peer_reviewed", "abstract", "patent", "database"],
                weights=[0.55, 0.2, 0.05, 0.20],
            )[0]
        )

        n_samples = {
            "cell_line": RNG.randint(1, 60),
            "xenograft": RNG.randint(6, 20),
            "pdx": RNG.randint(3, 12),
            "patient": RNG.randint(12, 220),
        }[model_type]

        indication = RNG.choice(INDICATIONS)
        year = RNG.randint(2015, 2025)

        dataset_id = {
            "peer_reviewed": f"PMID:{RNG.randint(28000000, 39999999)}",
            "abstract": f"AACR-{year}-{RNG.randint(1000, 9999)}",
            "patent": f"WO{year}{RNG.randint(100000, 999999)}A1",
            "database": RNG.choice(["DepMap-23Q4", "GDSC2", "CTRPv2", f"GSE{RNG.randint(100000, 260000)}"]),
            "internal_aprea": f"APR-INT-{RNG.randint(100, 999)}",
        }[source_type]

        rows.append(
            Evidence(
                source_type=source_type,
                citation=f"{'Aprea internal' if is_aprea else 'Public'} record #{i+1} ({year})",
                url_or_doi=None if is_aprea else f"https://doi.org/10.{RNG.randint(1000,9999)}/wee1.{i}",
                dataset_id=dataset_id,
                year=year,
                is_aprea_confidential=is_aprea,
                compound=compound,
                alias=alias,
                dose=RNG.choice(["30 mg/kg", "60 mg/kg", "200 mg BID", "300 mg QD", None]),
                schedule=RNG.choice(["5 days on / 2 off", "QDx5", "days 1-3 weekly", None]),
                combo_partner=combo,
                is_monotherapy=is_mono,
                indication=indication,
                histology=RNG.choice(["serous", "squamous", "adenocarcinoma", None]),
                treatment_setting=(
                    RNG.choice(["1st-line", "refractory", "maintenance", "2nd-line+"])
                    if model_type == "patient"
                    else "n/a (preclinical)"
                ),
                model_type=model_type,
                model_id=(
                    RNG.choice(["OVCAR-3", "Kuramochi", "MDA-MB-231", "H82", "SW620", "PDX-114"])
                    if model_type != "patient"
                    else f"Cohort-{RNG.randint(1,40)}"
                ),
                n=n_samples,
                population_description=f"{indication} ({model_type})",
                biomarker_name=bm_name,
                biomarker_type=profile["btype"],
                assay=RNG.choice(["NGS panel", "WES", "RNA-seq", "IHC", "WB", "mass-spec"]),
                cutoff=RNG.choice(["CN>=8", "TPM>median", "H-score>=200", "VAF>=5%", None]),
                biomarker_status=RNG.choice(["positive", "high", "low", "negative"]),
                response_metric=metric,
                response_value=value,
                units=units,
                direction=direction,
                effect_size=effect,
                effect_size_type=est,
                p_value=p,
                q_value=q,
                ci_low=round(effect - RNG.uniform(0.05, 0.2), 3),
                ci_high=round(effect + RNG.uniform(0.05, 0.2), 3),
                reproducibility=reproducibility,
                predictive_vs_prognostic=pred,
                wee1_specific_vs_combo=attribution,
                baseline_vs_pd=base_vs_pd,
                evidence_tier=SOURCE_TIERS[model_type],
                notes=None,
            )
        )
    return rows
