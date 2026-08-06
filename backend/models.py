"""
Data model for the WEE1 evidence matrix.

Each row in the `evidence` table is ONE atomic observation, matching the
"evidence matrix" fact-table design from the project primer:

    (study x compound x model/population x biomarker x outcome)

The field groups (provenance / compound / context / model / biomarker /
response / evidence-quality) mirror the data dictionary. See
`../DATA_DICTIONARY.md` (at the app root) for the authoritative definition of
every column, its type, units, and allowed values.
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class EvidenceBase(SQLModel):
    # --- Provenance -------------------------------------------------------
    source_type: str = Field(
        index=True,
        description="peer_reviewed | abstract | patent | database | internal_aprea",
    )
    citation: str = Field(description="Human-readable source (author/year/title or dataset).")
    url_or_doi: Optional[str] = Field(default=None, description="DOI or stable URL.")
    dataset_id: Optional[str] = Field(
        default=None, index=True, description="e.g. NCT id, GSE id, DepMap release, PMID."
    )
    year: Optional[int] = Field(default=None, index=True)
    is_aprea_confidential: bool = Field(
        default=False,
        index=True,
        description="TRUE = confidential Aprea data, kept segregated from public evidence.",
    )

    # --- Compound / regimen ----------------------------------------------
    compound: str = Field(index=True, description="Canonical WEE1 inhibitor name.")
    alias: Optional[str] = Field(default=None, description="e.g. MK-1775, AZD1775, ZN-c3.")
    dose: Optional[str] = Field(default=None)
    schedule: Optional[str] = Field(default=None)
    combo_partner: Optional[str] = Field(
        default=None, index=True, description="Combination drug, or null for monotherapy."
    )
    is_monotherapy: bool = Field(default=True, index=True)

    # --- Context ----------------------------------------------------------
    indication: str = Field(index=True, description="Cancer type (OncoTree-style label).")
    histology: Optional[str] = Field(default=None)
    treatment_setting: Optional[str] = Field(
        default=None, description="e.g. 1st-line, refractory, maintenance, n/a (preclinical)."
    )
    model_type: str = Field(
        index=True, description="cell_line | xenograft | pdx | patient"
    )

    # --- Model / population ----------------------------------------------
    model_id: Optional[str] = Field(default=None, description="Cell line / PDX / cohort id.")
    n: Optional[int] = Field(default=None, description="Sample size (cell lines, animals, patients).")
    population_description: Optional[str] = Field(default=None)

    # --- Biomarker --------------------------------------------------------
    biomarker_name: str = Field(index=True, description="e.g. CCNE1 amplification, TP53 mutation.")
    biomarker_type: str = Field(
        index=True, description="mutation | cnv | expression | protein | phospho | signature"
    )
    assay: Optional[str] = Field(default=None, description="How the biomarker was measured.")
    cutoff: Optional[str] = Field(default=None, description="Threshold for calling positive.")
    biomarker_status: Optional[str] = Field(
        default=None, description="positive | negative | high | low | continuous"
    )

    # --- Response / outcome ----------------------------------------------
    response_metric: str = Field(
        index=True, description="IC50 | AUC | TGI | ORR | PFS | DoR | HR | dependency"
    )
    response_value: Optional[float] = Field(default=None)
    units: Optional[str] = Field(default=None, description="nM, %, months, unitless, etc.")
    direction: Optional[str] = Field(
        default=None, index=True, description="sensitive | resistant | neutral"
    )

    # --- Evidence quality / classification -------------------------------
    effect_size: Optional[float] = Field(
        default=None, description="r, Cohen's d, odds ratio, or hazard ratio (see effect_size_type)."
    )
    effect_size_type: Optional[str] = Field(
        default=None, description="pearson_r | cohens_d | odds_ratio | hazard_ratio | fold_change"
    )
    p_value: Optional[float] = Field(default=None)
    q_value: Optional[float] = Field(default=None, description="FDR-corrected p-value.")
    ci_low: Optional[float] = Field(default=None)
    ci_high: Optional[float] = Field(default=None)
    reproducibility: Optional[str] = Field(
        default=None,
        index=True,
        description="single_dataset | multi_dataset | reproducible",
    )
    predictive_vs_prognostic: Optional[str] = Field(
        default=None, index=True, description="predictive | prognostic | unclear"
    )
    wee1_specific_vs_combo: Optional[str] = Field(
        default=None,
        index=True,
        description="wee1_specific | combo_driven | unclear",
    )
    baseline_vs_pd: Optional[str] = Field(
        default=None, index=True, description="baseline | pharmacodynamic"
    )
    evidence_tier: Optional[str] = Field(
        default=None,
        index=True,
        description="preclinical_invitro | preclinical_invivo | clinical",
    )
    notes: Optional[str] = Field(default=None)


class Evidence(EvidenceBase, table=True):
    """The database table."""

    id: Optional[int] = Field(default=None, primary_key=True)


class EvidenceCreate(EvidenceBase):
    """Request body for creating a row (all base fields, no id)."""


class EvidenceRead(EvidenceBase):
    """Response body (base fields + id)."""

    id: int


class EvidenceUpdate(SQLModel):
    """Partial update: every field optional. Only provided fields change."""

    source_type: Optional[str] = None
    citation: Optional[str] = None
    url_or_doi: Optional[str] = None
    dataset_id: Optional[str] = None
    year: Optional[int] = None
    is_aprea_confidential: Optional[bool] = None
    compound: Optional[str] = None
    alias: Optional[str] = None
    dose: Optional[str] = None
    schedule: Optional[str] = None
    combo_partner: Optional[str] = None
    is_monotherapy: Optional[bool] = None
    indication: Optional[str] = None
    histology: Optional[str] = None
    treatment_setting: Optional[str] = None
    model_type: Optional[str] = None
    model_id: Optional[str] = None
    n: Optional[int] = None
    population_description: Optional[str] = None
    biomarker_name: Optional[str] = None
    biomarker_type: Optional[str] = None
    assay: Optional[str] = None
    cutoff: Optional[str] = None
    biomarker_status: Optional[str] = None
    response_metric: Optional[str] = None
    response_value: Optional[float] = None
    units: Optional[str] = None
    direction: Optional[str] = None
    effect_size: Optional[float] = None
    effect_size_type: Optional[str] = None
    p_value: Optional[float] = None
    q_value: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    reproducibility: Optional[str] = None
    predictive_vs_prognostic: Optional[str] = None
    wee1_specific_vs_combo: Optional[str] = None
    baseline_vs_pd: Optional[str] = None
    evidence_tier: Optional[str] = None
    notes: Optional[str] = None
