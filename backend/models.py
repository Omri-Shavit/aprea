"""SQLModel schema for the DDR evidence matrix.

Two tables:

  * ``Compound``  - the controlled drug dictionary (STEP 1 of the program brief).
                    One row per DDR-targeting agent, annotated with selectivity,
                    dose, schedule and known off-target activity.
  * ``Evidence``  - the fact table. One row is a single atomic observation
                    following the evidence model from the brief:

        compound -> regimen -> cancer type -> specimen -> molecular feature
                 -> response endpoint -> effect size -> evidence level

Controlled vocabularies live in ``vocabulary.py`` and are documented in
``DATA_DICTIONARY.md``. Edit the data dictionary first, then mirror here.
"""

from typing import Optional

from sqlmodel import Field, SQLModel

# ---------------------------------------------------------------------------
# Drug dictionary
# ---------------------------------------------------------------------------


class CompoundBase(SQLModel):
    """One DDR-targeting agent, with the annotations the brief requires."""

    canonical_name: str = Field(index=True, description="Preferred (INN) name, e.g. adavosertib.")
    aliases: Optional[str] = Field(
        default=None,
        description="Semicolon-delimited alternate names, e.g. 'MK-1775; AZD1775'.",
    )

    target: str = Field(index=True, description="Primary DDR target, e.g. WEE1, ATR, PARP.")
    target_family: Optional[str] = Field(
        default=None,
        index=True,
        description="Target grouping: checkpoint_kinase | pikk | parp_family | polymerase | "
        "deubiquitinase | kinase_other.",
    )
    secondary_targets: Optional[str] = Field(
        default=None, description="Other targets engaged at therapeutic concentrations."
    )

    developer: Optional[str] = Field(default=None, description="Sponsor / originator.")
    clinical_stage: Optional[str] = Field(
        default=None,
        index=True,
        description="preclinical_tool | phase_1 | phase_2 | phase_3 | approved | discontinued.",
    )

    selectivity: Optional[str] = Field(
        default=None, description="Selectivity summary (e.g. 'WEE1-selective; >100x vs PLK1')."
    )
    off_target_activity: Optional[str] = Field(
        default=None, description="Known off-target pharmacology relevant to interpretation."
    )
    typical_dose: Optional[str] = Field(default=None, description="e.g. '300 mg QD'.")
    typical_schedule: Optional[str] = Field(default=None, description="e.g. '5 days on / 2 off'.")

    chembl_id: Optional[str] = Field(default=None)
    is_tool_compound: bool = Field(
        default=False,
        index=True,
        description="TRUE = preclinical probe, not a development candidate.",
    )
    notes: Optional[str] = Field(default=None)


class Compound(CompoundBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class CompoundCreate(CompoundBase):
    pass


class CompoundRead(CompoundBase):
    id: int


# ---------------------------------------------------------------------------
# Evidence fact table
# ---------------------------------------------------------------------------


class EvidenceBase(SQLModel):
    """One atomic observation linking a regimen to a molecular feature and an outcome."""

    # -- Provenance ---------------------------------------------------------
    source_type: str = Field(
        index=True,
        description="peer_reviewed | abstract | patent | database | registry | preprint.",
    )
    citation: str = Field(description="Human-readable source (author/year/title or dataset).")
    url_or_doi: Optional[str] = Field(default=None, description="DOI or stable URL.")
    dataset_id: Optional[str] = Field(
        default=None, index=True, description="NCT id, PMID, GSE id, GDSC drug id, DepMap release."
    )
    year: Optional[int] = Field(default=None, index=True)

    # -- Target & compound --------------------------------------------------
    target: str = Field(
        index=True,
        description="DDR target of the primary agent: WEE1 | ATR | ATM | CHK1 | DNA-PK | PARP | "
        "PKMYT1 | POLQ | USP1 | DYRK1A | DYRK1B | RAD51 | multi.",
    )
    target_family: Optional[str] = Field(
        default=None, index=True, description="checkpoint_kinase | pikk | parp_family | ..."
    )
    compound: str = Field(index=True, description="Canonical agent name (FK by name to Compound).")
    alias: Optional[str] = Field(default=None, description="Name as written in the source.")
    dose: Optional[str] = Field(default=None)
    schedule: Optional[str] = Field(default=None)

    # -- Regimen (the four analysis tracks from the brief) ------------------
    combination_track: str = Field(
        default="monotherapy",
        index=True,
        description="monotherapy | chemotherapy | radiotherapy | targeted_agent. The four "
        "tracks the analysis must keep separate.",
    )
    combo_partner: Optional[str] = Field(
        default=None, index=True, description="Partner agent/modality, or null for monotherapy."
    )
    combo_partner_target: Optional[str] = Field(
        default=None, description="Partner's target/class (e.g. PARP, platinum, radiation)."
    )
    is_monotherapy: bool = Field(default=True, index=True)

    # -- Cancer type --------------------------------------------------------
    indication: str = Field(index=True, description="Specific cancer type (OncoTree-style label).")
    indication_category: Optional[str] = Field(
        default=None,
        index=True,
        description="Broad grouping: gynecologic | thoracic | gi | breast | gu | head_neck | "
        "cns | sarcoma | heme | skin | pan_cancer | other.",
    )
    histology: Optional[str] = Field(default=None)
    treatment_setting: Optional[str] = Field(
        default=None,
        index=True,
        description="1st-line | 2nd-line+ | refractory | maintenance | n/a (preclinical).",
    )
    prior_therapies: Optional[str] = Field(
        default=None, description="Prior treatment exposure - a key confounder for response."
    )

    # -- Model / population -------------------------------------------------
    model_type: str = Field(index=True, description="cell_line | organoid | xenograft | pdx | patient.")
    model_id: Optional[str] = Field(default=None, description="Cell line / PDX / cohort id.")
    n: Optional[int] = Field(default=None, description="Sample size (cell lines, animals, patients).")
    population_description: Optional[str] = Field(default=None)
    perturbation_type: str = Field(
        default="chemical",
        index=True,
        description="chemical (small molecule) | genetic (CRISPR/RNAi dependency). Agreement "
        "between the two is what separates target biology from compound off-target effects.",
    )

    # -- Specimen -----------------------------------------------------------
    specimen_type: Optional[str] = Field(
        default=None,
        index=True,
        description="tumor_tissue | plasma_ctdna | whole_blood | pbmc | skin_biopsy | "
        "cell_pellet | n/a.",
    )
    specimen_timing: Optional[str] = Field(
        default=None,
        index=True,
        description="baseline | on_treatment | progression | not_reported. Specimen timing is a "
        "priority extraction field in the brief.",
    )

    # -- Molecular feature (biomarker) --------------------------------------
    biomarker_name: str = Field(index=True, description="e.g. CCNE1 amplification, TP53 mutation.")
    biomarker_type: str = Field(
        index=True, description="mutation | cnv | expression | protein | phospho | signature | fusion."
    )
    biomarker_scope: Optional[str] = Field(
        default=None,
        index=True,
        description="tumor_specific | tumor_agnostic. The brief asks for both to be identified.",
    )
    assay: Optional[str] = Field(default=None, description="How the biomarker was measured.")
    assay_modality: Optional[str] = Field(
        default=None,
        index=True,
        description="ngs | ihc | rna | liquid_biopsy | proteomics | functional. Drives the "
        "assay-feasibility scoring dimension.",
    )
    cutoff: Optional[str] = Field(default=None, description="Threshold for calling positive.")
    biomarker_status: Optional[str] = Field(
        default=None, description="positive | negative | high | low | continuous."
    )

    # -- Response endpoint --------------------------------------------------
    response_metric: str = Field(
        index=True,
        description="ORR | RECIST_response | DoR | PFS | OS | CBR_6mo | ctDNA_reduction | "
        "IC50 | AUC | GI50 | TGI | HR | dependency_score.",
    )
    response_value: Optional[float] = Field(default=None)
    units: Optional[str] = Field(default=None, description="nM, uM, %, months, unitless, etc.")
    endpoint_class: Optional[str] = Field(
        default=None,
        index=True,
        description="primary (objective response by RECIST) | secondary (DoR, PFS, 6-month "
        "clinical benefit, early ctDNA reduction) | exploratory | preclinical.",
    )
    direction: Optional[str] = Field(
        default=None, index=True, description="sensitive | resistant | neutral."
    )

    # -- Effect size --------------------------------------------------------
    effect_size: Optional[float] = Field(
        default=None, description="See effect_size_type for the scale."
    )
    effect_size_type: Optional[str] = Field(
        default=None,
        description="pearson_r | spearman_rho | cohens_d | odds_ratio | hazard_ratio | "
        "fold_change | delta_auc.",
    )
    p_value: Optional[float] = Field(default=None)
    q_value: Optional[float] = Field(default=None, description="FDR-corrected p-value.")
    ci_low: Optional[float] = Field(default=None)
    ci_high: Optional[float] = Field(default=None)

    # -- Evidence level -----------------------------------------------------
    evidence_tier: Optional[str] = Field(
        default=None,
        index=True,
        description="preclinical_invitro | preclinical_invivo | clinical.",
    )
    reproducibility: Optional[str] = Field(
        default=None, index=True, description="single_dataset | multi_dataset | reproducible."
    )
    predictive_vs_prognostic: Optional[str] = Field(
        default=None, index=True, description="predictive | prognostic | unclear."
    )
    evidence_basis: Optional[str] = Field(
        default=None,
        index=True,
        description="randomized_interaction | single_arm_association | responder_only | "
        "preclinical_correlation. Only randomized_interaction supports a genuine claim of "
        "predictiveness; responder_only findings stay hypothesis-generating.",
    )
    target_specific_vs_combo: Optional[str] = Field(
        default=None,
        index=True,
        description="target_specific | combo_driven | unclear. Can the signal be attributed to "
        "the DDR agent rather than its combination partner?",
    )
    baseline_vs_pd: Optional[str] = Field(
        default=None, index=True, description="baseline (selection) | pharmacodynamic (target engagement)."
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
    """Partial update - every field optional."""

    source_type: Optional[str] = None
    citation: Optional[str] = None
    url_or_doi: Optional[str] = None
    dataset_id: Optional[str] = None
    year: Optional[int] = None

    target: Optional[str] = None
    target_family: Optional[str] = None
    compound: Optional[str] = None
    alias: Optional[str] = None
    dose: Optional[str] = None
    schedule: Optional[str] = None

    combination_track: Optional[str] = None
    combo_partner: Optional[str] = None
    combo_partner_target: Optional[str] = None
    is_monotherapy: Optional[bool] = None

    indication: Optional[str] = None
    indication_category: Optional[str] = None
    histology: Optional[str] = None
    treatment_setting: Optional[str] = None
    prior_therapies: Optional[str] = None

    model_type: Optional[str] = None
    model_id: Optional[str] = None
    n: Optional[int] = None
    population_description: Optional[str] = None
    perturbation_type: Optional[str] = None

    specimen_type: Optional[str] = None
    specimen_timing: Optional[str] = None

    biomarker_name: Optional[str] = None
    biomarker_type: Optional[str] = None
    biomarker_scope: Optional[str] = None
    assay: Optional[str] = None
    assay_modality: Optional[str] = None
    cutoff: Optional[str] = None
    biomarker_status: Optional[str] = None

    response_metric: Optional[str] = None
    response_value: Optional[float] = None
    units: Optional[str] = None
    endpoint_class: Optional[str] = None
    direction: Optional[str] = None

    effect_size: Optional[float] = None
    effect_size_type: Optional[str] = None
    p_value: Optional[float] = None
    q_value: Optional[float] = None
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None

    evidence_tier: Optional[str] = None
    reproducibility: Optional[str] = None
    predictive_vs_prognostic: Optional[str] = None
    evidence_basis: Optional[str] = None
    target_specific_vs_combo: Optional[str] = None
    baseline_vs_pd: Optional[str] = None
    notes: Optional[str] = None
