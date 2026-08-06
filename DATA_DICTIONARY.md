# WEE1 Evidence Matrix — Data Dictionary

The authoritative schema for the evidence matrix. Each row in the `evidence`
table is **one atomic observation**: a single (study × compound × model/population
× biomarker × outcome) tuple. This document defines every field, its type, units,
and allowed values (the controlled vocabulary). When extending the schema, edit
this file first, then mirror the change in `backend/models.py`.

Legend: **type** uses `str`, `int`, `float`, `bool`. "Allowed values" lists the
controlled vocabulary; where it says *free text* the field is uncontrolled.

## Provenance

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `id` | int | auto | — | Primary key (assigned by DB). |
| `source_type` | str | ✓ | — | `peer_reviewed`, `abstract`, `patent`, `database`, `internal_aprea`. Separates peer-reviewed evidence from abstracts/patents/etc. |
| `citation` | str | ✓ | — | *Free text* — author/year/title or dataset name. |
| `url_or_doi` | str | | — | DOI or stable URL. |
| `dataset_id` | str | | — | Stable id: NCT number, GSE accession, PMID, DepMap release, etc. |
| `year` | int | | year | Publication/release year. |
| `is_aprea_confidential` | bool | ✓ | — | `true` = confidential Aprea data, kept segregated. Default `false`. |

## Compound / regimen

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `compound` | str | ✓ | — | Canonical WEE1 inhibitor name (e.g. `adavosertib`, `azenosertib`). |
| `alias` | str | | — | Alternate name (e.g. `MK-1775`, `AZD1775`, `ZN-c3`). |
| `dose` | str | | — | *Free text* (e.g. `60 mg/kg`, `300 mg QD`). |
| `schedule` | str | | — | *Free text* (e.g. `5 days on / 2 off`). |
| `combo_partner` | str | | — | Combination drug; null for monotherapy. |
| `is_monotherapy` | bool | ✓ | — | `true` if single-agent. Default `true`. |

## Context

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `indication` | str | ✓ | — | Cancer type (OncoTree-style label). |
| `histology` | str | | — | *Free text* (e.g. `serous`, `squamous`). |
| `treatment_setting` | str | | — | `1st-line`, `2nd-line+`, `refractory`, `maintenance`, `n/a (preclinical)`. |
| `model_type` | str | ✓ | — | `cell_line`, `xenograft`, `pdx`, `patient`. |

## Model / population

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `model_id` | str | | — | Cell-line / PDX / cohort identifier. |
| `n` | int | | count | Sample size (cell lines, animals, or patients). |
| `population_description` | str | | — | *Free text*. |

## Biomarker

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `biomarker_name` | str | ✓ | — | e.g. `CCNE1 amplification`, `TP53 mutation`, `SLFN11 high expression`. Use HGNC gene symbols. |
| `biomarker_type` | str | ✓ | — | `mutation`, `cnv`, `expression`, `protein`, `phospho`, `signature`. |
| `assay` | str | | — | How it was measured (e.g. `NGS panel`, `RNA-seq`, `IHC`, `mass-spec`). |
| `cutoff` | str | | — | Threshold for calling positive (e.g. `CN>=8`, `H-score>=200`). |
| `biomarker_status` | str | | — | `positive`, `negative`, `high`, `low`, `continuous`. |

## Response / outcome

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `response_metric` | str | ✓ | — | `IC50`, `AUC`, `TGI`, `ORR`, `PFS`, `DoR`, `HR`, `dependency`. |
| `response_value` | float | | see `units` | The measured value. |
| `units` | str | | — | `nM`, `%`, `months`, `unitless`. **Harmonize before comparing.** |
| `direction` | str | | — | `sensitive`, `resistant`, `neutral`. Interprets the response for this biomarker. |

## Evidence quality / classification

These fields encode the distinctions the project brief insists on. They are the
categorical dimensions used to slice and rank the evidence.

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `effect_size` | float | | see type | Magnitude of the biomarker↔response association. |
| `effect_size_type` | str | | — | `pearson_r`, `cohens_d`, `odds_ratio`, `hazard_ratio`, `fold_change`. **Different scales — do not compare across types naively.** |
| `p_value` | float | | — | Raw significance (0–1). |
| `q_value` | float | | — | FDR-corrected p-value. Prefer this when many features were tested. |
| `ci_low` / `ci_high` | float | | — | 95% confidence interval on the effect size. |
| `reproducibility` | str | | — | `single_dataset`, `multi_dataset`, `reproducible`. Guards against single-dataset overfitting. |
| `predictive_vs_prognostic` | str | | — | `predictive` (changes treatment benefit — interaction term), `prognostic` (outcome regardless of treatment — main effect), `unclear`. |
| `wee1_specific_vs_combo` | str | | — | `wee1_specific`, `combo_driven`, `unclear`. Attribution when a partner drug is present. |
| `baseline_vs_pd` | str | | — | `baseline` (selection biomarker, pre-treatment) vs `pharmacodynamic` (on-treatment mechanism readout). |
| `evidence_tier` | str | | — | `preclinical_invitro` < `preclinical_invivo` < `clinical` (increasing weight). |
| `notes` | str | | — | *Free text*. |

## Derived / analytics (not stored — computed by `insights.py`)

| Name | Where | Definition |
|---|---|---|
| `composite_score` | biomarker-ranking | `mean(|effect|) × reproducibility_weight × tier_weight × source_weight × (0.4 + 0.6·directional_consistency) × (0.5 + 0.5·log_support)` |
| `frac_sensitive` | ranking / landscape | fraction of a group's observations with `direction == sensitive` |
| `neg_log10_p` | volcano | `-log10(max(p_value, 1e-6))` |

## Conventions & caveats

- **Entity resolution**: map compound aliases to a canonical `compound`, and gene
  names to HGNC symbols, before insert. The alias problem (MK-1775 = AZD1775 =
  adavosertib) is handled by storing canonical `compound` + `alias`.
- **Unit harmonization**: `response_value` is only comparable within the same
  `response_metric` + `units`. IC50 (nM) is *not* comparable to AUC (unitless).
- **Effect-size scales**: `pearson_r`, `cohens_d`, and `hazard_ratio` live on
  different scales. Ranking that mixes them (as this mockup's default does) is a
  known simplification — segment by `effect_size_type` for rigorous comparison.
- **Directionality**: for `IC50`/`AUC`/`HR`, lower is "more sensitive"; for
  `TGI`/`ORR`/`PFS`, higher is "more sensitive". The `direction` field records the
  interpreted call so downstream code doesn't re-derive it.
