# DDR Evidence Matrix — Data Dictionary

The authoritative schema for the DNA-damage-response (DDR) evidence matrix,
covering all DDR targets — WEE1, ATR, ATM, CHK1/2, DNA-PK, PARP, PKMYT1, POLQ,
USP1, DYRK1A/B, RAD51, APEX1 — not WEE1 alone.

There are **two tables**:

| Table | Grain | Purpose |
|---|---|---|
| `compound` | one row per DDR-targeting agent | The controlled drug dictionary (STEP 1 of the program brief): selectivity, stage, dose/schedule, off-target activity. |
| `evidence` | one row per atomic observation | The fact table: a single (study × compound × regimen × cancer type × specimen × biomarker × outcome) tuple. |

The evidence model reads left to right:

```
compound → regimen → cancer type → specimen → molecular feature
         → response endpoint → effect size → evidence level
```

This document defines every field, its type, units, and allowed values (the
controlled vocabulary). When extending the schema, **edit this file first**,
then mirror the change in `backend/models.py` and `backend/vocabulary.py`.

Legend: **type** uses `str`, `int`, `float`, `bool`. "Allowed values" lists the
controlled vocabulary; where it says *free text* the field is uncontrolled.
Controlled lists are defined once in `backend/vocabulary.py` and served to the
UI by `GET /api/vocab`.

---

# Table 1 — `compound` (drug dictionary)

One row per agent. The evidence table joins to it **by name**
(`evidence.compound` → `compound.canonical_name`); there is no enforced foreign
key, so entity resolution happens at ingestion time.

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `id` | int | auto | — | Primary key (assigned by DB). |
| `canonical_name` | str | ✓ | — | Preferred (INN) name, e.g. `adavosertib`. All evidence rows must use this spelling. |
| `aliases` | str | | — | Semicolon-delimited alternates, e.g. `MK-1775; AZD1775`. |
| `target` | str | ✓ | — | Primary DDR target. `WEE1`, `ATR`, `ATM`, `CHK1`, `CHK2`, `DNA-PK`, `PARP`, `PARP7`, `PKMYT1`, `POLQ`, `POLA1`, `USP1`, `DYRK1A`, `DYRK1B`, `RAD51`, `APEX1`, `multi`. |
| `target_family` | str | | — | `checkpoint_kinase`, `pikk`, `parp_family`, `polymerase`, `deubiquitinase`, `recombinase`, `ber_enzyme`, `kinase_other`, `multi_target`. Derived from `target` when omitted. |
| `secondary_targets` | str | | — | *Free text* — other targets engaged at therapeutic concentrations. |
| `developer` | str | | — | Sponsor / originator. |
| `clinical_stage` | str | | — | `preclinical_tool`, `phase_1`, `phase_2`, `phase_3`, `approved`, `discontinued`. |
| `selectivity` | str | | — | *Free text* summary, e.g. `WEE1-selective; >100x vs PLK1`. |
| `off_target_activity` | str | | — | *Free text* — known off-target pharmacology relevant to interpreting a signal. |
| `typical_dose` | str | | — | *Free text*, e.g. `300 mg QD`. |
| `typical_schedule` | str | | — | *Free text*, e.g. `5 days on / 2 off`. |
| `chembl_id` | str | | — | ChEMBL identifier. |
| `is_tool_compound` | bool | ✓ | — | `true` = preclinical probe, not a development candidate. Default `false`. Filterable via `GET /api/compounds?include_tool_compounds=false`. |
| `notes` | str | | — | *Free text*. |

---

# Table 2 — `evidence` (fact table)

## Provenance

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `id` | int | auto | — | Primary key (assigned by DB). |
| `source_type` | str | ✓ | — | `peer_reviewed`, `abstract`, `patent`, `database`, `registry`, `preprint`. Separates peer-reviewed evidence from abstracts, patents, registry postings and preprints. |
| `citation` | str | ✓ | — | *Free text* — author/year/title or dataset name. |
| `url_or_doi` | str | | — | DOI or stable URL. |
| `dataset_id` | str | | — | Stable id: `NCT…` number, PMID, GSE accession, GDSC drug id, DepMap release. **Doubles as the reproducibility key** — distinct `dataset_id`s are what the ranking counts as independent support, and `NCT…` prefixes are what `summary.n_trials` counts. |
| `year` | int | | year | Publication / release year. |

## Target & compound

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `target` | str | ✓ | — | DDR target of the primary agent. Same vocabulary as `compound.target` (see above). `multi` for agents without a single dominant target. |
| `target_family` | str | | — | Same vocabulary as `compound.target_family`. Derived from `target` on write when omitted. |
| `compound` | str | ✓ | — | Canonical agent name — joins by name to `compound.canonical_name`. |
| `alias` | str | | — | The name exactly as written in the source (e.g. `MK-1775`, `ZN-c3`). Preserved for traceability. |
| `dose` | str | | — | *Free text* (e.g. `60 mg/kg`, `300 mg QD`). |
| `schedule` | str | | — | *Free text* (e.g. `5 days on / 2 off`). |

## Regimen (the four analysis tracks)

The brief requires these four tracks be analysed **separately** — a biomarker
of benefit under monotherapy is a different claim from a biomarker of benefit
under chemotherapy combination.

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `combination_track` | str | ✓ | — | `monotherapy`, `chemotherapy`, `radiotherapy`, `targeted_agent`. Default `monotherapy`. |
| `combo_partner` | str | | — | Partner agent or modality (e.g. `carboplatin`, `radiation`, `olaparib`); null for monotherapy. |
| `combo_partner_target` | str | | — | The partner's target or class (e.g. `PARP`, `platinum`, `radiation`). Needed to reason about the attribution problem. |
| `is_monotherapy` | bool | ✓ | — | `true` if single-agent. Default `true`. |

**Consistency rule (enforced on write, by normalization not rejection).** The
API reconciles these three fields so they can never disagree:

- a non-`monotherapy` track ⇒ `is_monotherapy = false`;
- the default `monotherapy` track *with* a named `combo_partner` ⇒ the track is
  inferred from the partner name (radiotherapy keywords first, so
  "chemoradiation" lands in `radiotherapy`, then chemotherapy keywords,
  otherwise `targeted_agent`) and `is_monotherapy = false`;
- the `monotherapy` track with no named partner ⇒ `is_monotherapy = true`.

## Cancer type

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `indication` | str | ✓ | — | Specific cancer type (OncoTree-style label), e.g. `high-grade serous ovarian cancer`. |
| `indication_category` | str | | — | Broad grouping: `gynecologic`, `thoracic`, `gi`, `breast`, `gu`, `head_neck`, `cns`, `sarcoma`, `heme`, `skin`, `endocrine`, `pan_cancer`, `other`. Derived from `indication` by `vocabulary.categorize_indication()` when omitted. |
| `histology` | str | | — | *Free text* (e.g. `serous`, `squamous`). |
| `treatment_setting` | str | | — | `1st-line`, `2nd-line+`, `refractory`, `maintenance`, `n/a (preclinical)`. |
| `prior_therapies` | str | | — | *Free text* — prior treatment exposure. A key confounder for response, especially prior platinum or prior PARP inhibitor. |

## Model / population

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `model_type` | str | ✓ | — | `cell_line`, `organoid`, `xenograft`, `pdx`, `patient`. |
| `model_id` | str | | — | Cell-line / PDX / cohort identifier. |
| `n` | int | | count | Sample size (cell lines, animals, or patients). **Not comparable across `model_type`** — see caveats. |
| `population_description` | str | | — | *Free text*. |
| `perturbation_type` | str | ✓ | — | `chemical` (small-molecule inhibition) or `genetic` (CRISPR/RNAi dependency). Default `chemical`. Agreement between the two is what separates target biology from compound off-target effects. |

## Specimen

Specimen type and timing are priority extraction fields in the brief: without
them a "biomarker" cannot be placed as a selection marker versus a
pharmacodynamic readout.

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `specimen_type` | str | | — | `tumor_tissue`, `plasma_ctdna`, `whole_blood`, `pbmc`, `skin_biopsy`, `cell_pellet`, `n/a`. |
| `specimen_timing` | str | | — | `baseline`, `on_treatment`, `progression`, `not_reported`. |

## Molecular feature (biomarker)

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `biomarker_name` | str | ✓ | — | e.g. `CCNE1 amplification`, `TP53 mutation`, `SLFN11 high expression`. Use HGNC gene symbols. **This is the grouping key for the biomarker ranking**, so spelling must be harmonized at ingestion. |
| `biomarker_type` | str | ✓ | — | `mutation`, `cnv`, `expression`, `protein`, `phospho`, `signature`, `fusion`. |
| `biomarker_scope` | str | | — | `tumor_specific` or `tumor_agnostic`. The brief asks for both classes to be identified explicitly. |
| `assay` | str | | — | *Free text* — how it was measured (e.g. `FoundationOne CDx`, `RNA-seq`, `IHC H-score`). |
| `assay_modality` | str | | — | `ngs`, `ihc`, `rna`, `liquid_biopsy`, `proteomics`, `functional`. Drives the assay-feasibility scoring dimension. |
| `cutoff` | str | | — | Threshold for calling positive (e.g. `CN>=8`, `H-score>=200`). |
| `biomarker_status` | str | | — | `positive`, `negative`, `high`, `low`, `continuous`. |

## Response endpoint

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `response_metric` | str | ✓ | — | Clinical: `ORR`, `RECIST_response`, `DoR`, `PFS`, `OS`, `CBR_6mo`, `ctDNA_reduction`, `HR`. Preclinical: `IC50`, `AUC`, `GI50`, `TGI`, `dependency_score`, `viability`. |
| `response_value` | float | | see `units` | The measured value. |
| `units` | str | | — | `nM`, `uM`, `%`, `months`, `unitless`, … **Harmonize before comparing.** |
| `endpoint_class` | str | | — | `primary` (objective response by RECIST — `ORR`, `RECIST_response`), `secondary` (`DoR`, `PFS`, `OS`, `CBR_6mo`, `ctDNA_reduction`), `preclinical`, `exploratory`. Derived from `response_metric` by `vocabulary.endpoint_class_for()` when omitted. |
| `direction` | str | | — | `sensitive`, `resistant`, `neutral`. The interpreted call for this biomarker, so downstream code never re-derives it. |

## Effect size

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `effect_size` | float | | see type | Magnitude of the biomarker↔response association. |
| `effect_size_type` | str | | — | `pearson_r`, `spearman_rho`, `cohens_d`, `odds_ratio`, `hazard_ratio`, `fold_change`, `delta_auc`. **Different scales — do not compare across types naively.** |
| `p_value` | float | | — | Raw significance (0–1). Frequently null in curated clinical rows; the API sorts nulls last rather than treating them as zero. |
| `q_value` | float | | — | FDR-corrected p-value. Prefer this when many features were tested. |
| `ci_low` / `ci_high` | float | | — | 95% confidence interval on the effect size. |

## Evidence level

These fields encode the distinctions the brief insists on. They are the
categorical dimensions used to slice, weight and rank the evidence.

| Field | Type | Req | Units | Allowed values / notes |
|---|---|---|---|---|
| `evidence_tier` | str | | — | `preclinical_invitro` < `preclinical_invivo` < `clinical` (increasing weight). |
| `reproducibility` | str | | — | `single_dataset`, `multi_dataset`, `reproducible`. Guards against single-dataset overfitting. |
| `predictive_vs_prognostic` | str | | — | `predictive` (changes treatment benefit — interaction term), `prognostic` (outcome regardless of treatment — main effect), `unclear`. |
| `evidence_basis` | str | | — | `randomized_interaction`, `single_arm_association`, `responder_only`, `preclinical_correlation`. **The study-design hierarchy.** Only `randomized_interaction` supports a genuine claim of predictiveness; `responder_only` findings stay hypothesis-generating. |
| `target_specific_vs_combo` | str | | — | `target_specific`, `combo_driven`, `unclear`. Attribution: can the signal be assigned to the DDR agent rather than its combination partner? (Renamed from `wee1_specific_vs_combo` now that the matrix spans all DDR targets.) |
| `baseline_vs_pd` | str | | — | `baseline` (selection biomarker, pre-treatment) vs `pharmacodynamic` (on-treatment target-engagement readout). |
| `notes` | str | | — | *Free text*. |

---

# Derived / analytics (not stored — computed by `backend/insights.py`)

## The eight biomarker scoring dimensions

`GET /api/insights/biomarker-ranking` groups rows by `biomarker_name` and
scores each biomarker on the eight dimensions the brief specifies. Every
sub-score is normalized to **0–1** and returned individually alongside the
composite, so the UI can show the breakdown and a reviewer can disagree with a
single dimension rather than with an opaque number.

| # | Dimension | Weight | Computed from | Known limitation |
|---|---|---|---|---|
| 1 | `clinical_evidence` | 0.20 | `0.40·tier + 0.30·share(model_type = patient) + 0.30·basis`, using `TIER_WEIGHT` and `BASIS_WEIGHT` | A large single-arm trial and a small one score identically; size is handled by dimension 7. |
| 2 | `reproducibility` | 0.15 | `0.60·REPRO_WEIGHT + 0.40·saturate(n_distinct_dataset_id, 5)` | Rows lacking a `dataset_id` cannot contribute breadth (intentional, but penalizes poorly-provenanced sources). |
| 3 | `chemical_genetic_concordance` | 0.15 | `0` if only one `perturbation_type` present; else compare majority `direction` per modality: agree `1.0`, one modality has no call `0.5`, disagree `0.25` | A `0` means "not shown", not "shown false". Discordance scores above zero on purpose — the target was probed both ways. |
| 4 | `mechanistic_link` | 0.12 | `0.5·share(target_specific_vs_combo = target_specific) + 0.5·(biomarker_name matches REPLICATION_STRESS_FEATURES)` | The curated feature set (CCNE1/Cyclin E1, MYC, replication-stress signature, TP53, RB1/E2F, FBXW7, PPP2R1A, SLFN11, ATR/ATM, CHK1, PKMYT1, CDK1/CDK2, γH2AX, pCDK1) is a hand-maintained substring list: a genuinely novel mechanism scores half marks until added. |
| 5 | `attribution` | 0.12 | `share(is_monotherapy OR target_specific_vs_combo = target_specific)` | Treats monotherapy evidence as fully attributable, which ignores the possibility that the biomarker is purely prognostic. |
| 6 | `assay_feasibility` | 0.09 | `0.7·ASSAY_WEIGHT(assay_modality) + 0.3·BIOMARKER_TYPE_WEIGHT(biomarker_type)` | Ignores whether a validated, regulator-ready kit actually exists. |
| 7 | `validation_feasibility` | 0.09 | `0.4·SPECIMEN_WEIGHT + 0.3·TIMING_WEIGHT + 0.3·saturate(Σn, 300)` | `Σn` sums cohorts of very different kinds (cell lines and patients); treat as order-of-magnitude only. |
| 8 | `prevalence` | 0.08 | `0.6·saturate(n_distinct_indication, 6) + 0.4·saturate(n_distinct_indication_category, 4)` | **A coverage proxy, NOT true population prevalence.** Real prevalence needs per-indication alteration frequencies from GDC / cBioPortal / TCGA, which this schema does not hold. A biomarker studied only in ovarian cancer scores low even if highly prevalent there. |

**Composite formula** — a plain weighted mean, so each weight is exactly that
dimension's share of the final score:

```
composite_score = Σ  SCORE_WEIGHTS[d] · sub_score[d]        (weights sum to 1.0)
                 d∈dims
```

Weights live in the module-level `SCORE_WEIGHTS` dict in `backend/insights.py`
and are meant to be re-tuned; the supporting weight tables (`TIER_WEIGHT`,
`REPRO_WEIGHT`, `SOURCE_WEIGHT`, `BASIS_WEIGHT`, `ASSAY_WEIGHT`,
`BIOMARKER_TYPE_WEIGHT`, `SPECIMEN_WEIGHT`, `TIMING_WEIGHT`) sit alongside it.
`saturate(x, full) = min(1, log1p(x) / log1p(full))` is the diminishing-returns
transform that stops one heavily-studied biomarker from dominating.

**This ranking is hypothesis-generating.** A high composite means "worth
chasing", not "validated".

## Other derived values

| Name | Where | Definition |
|---|---|---|
| `frac_sensitive` | ranking / landscape / target-overview | Fraction of a group's observations with `direction == sensitive`. |
| `neg_log10_p` | volcano | `-log10(max(p_value, 1e-6))`. Only rows with **both** an effect size and a p-value are plotted. |
| `n_trials` | summary | Count of distinct `dataset_id`s beginning with `NCT`. |
| `pct_randomized_interaction` | summary | Share of rows with `evidence_basis == randomized_interaction` — the fraction of the matrix that can support a predictive claim at all. |
| `composite_relevance` | `GET /api/evidence?sort_by=` | Default sort: non-null `p_value` ascending first, then non-null `\|effect_size\|` descending, then `id`. Nulls are pushed last via an `IS NULL` sort key (portable across SQLite and Postgres) rather than being treated as zero. |
| `compounds_by_target` | `GET /api/vocab` | Distinct `(target, compound)` pairs present in `evidence`, keyed by target — powers the Target → Drug dropdown cascade. |
| `combo_partners_by_track` | `GET /api/vocab` | Distinct `combo_partner`s per `combination_track` — powers the Track → Partner cascade. |
| `target_overview` | `GET /api/insights/target-overview` | Per-target rollup: `n_rows`, `n_compounds`, `n_biomarkers`, `n_indications`, `n_clinical`, `frac_sensitive`, `top_biomarkers` (top 3 by supporting row count — a volume measure, deliberately not the ranking score). |

---

# Conventions & caveats

- **Predictive claims require randomization.** Per the program brief, a
  biomarker may be called genuinely **predictive** only on the basis of
  `evidence_basis == randomized_interaction` — a biomarker × treatment
  interaction tested in a randomized comparison. `single_arm_association`
  cannot separate predictive from prognostic (no control arm), `responder_only`
  analyses are selection-biased by construction, and
  `preclinical_correlation` is not human evidence. Everything below
  `randomized_interaction` is **hypothesis-generating** and must be labelled as
  such in any output shown to a decision-maker, regardless of how high it
  ranks.
- **Entity resolution**: map compound aliases to a canonical `compound`, and
  gene names to HGNC symbols, before insert. The alias problem
  (MK-1775 = AZD1775 = adavosertib) is handled by storing canonical `compound`
  + the source's `alias`, with the `compound` table as the authority. Because
  `biomarker_name` is the grouping key for the ranking, unharmonized spellings
  silently split one biomarker into two lower-ranked ones.
- **Unit harmonization**: `response_value` is only comparable within the same
  `response_metric` + `units`. IC50 (nM) is *not* comparable to AUC (unitless).
- **Effect-size scales**: `pearson_r`, `cohens_d` and `hazard_ratio` live on
  different scales, and a hazard ratio is not even centred on zero. Any ranking
  that mixes them is a known simplification — segment by `effect_size_type` for
  rigorous comparison. This is why `composite_relevance` sorts on `p_value`
  first and uses `|effect_size|` only as a tie-break.
- **Directionality**: for `IC50`/`AUC`/`GI50`/`HR`, lower is "more sensitive";
  for `TGI`/`ORR`/`PFS`/`DoR`, higher is "more sensitive". The `direction`
  field records the interpreted call so downstream code doesn't re-derive it.
- **Keep the four tracks separate**: `monotherapy`, `chemotherapy`,
  `radiotherapy` and `targeted_agent` evidence should not be pooled. Every
  `/api/insights/*` endpoint therefore accepts `target`, `combination_track`,
  `indication_category`, `evidence_tier` and `perturbation_type` scope filters.
- **`n` is not one thing**: `n = 120` cell lines and `n = 120` patients are
  incomparable. Always read `n` together with `model_type`.
- **Absence of data scores zero, not "unknown"**: sub-scores that depend on a
  field being populated (concordance, specimen feasibility) score 0 when the
  field is missing. Sparse curation therefore depresses a real biomarker's
  rank; check `n_studies` and `n_datasets` before concluding anything from a
  low composite.
- **No confidential tier.** The former `is_aprea_confidential` flag has been
  removed from the schema; the matrix holds externally-sourced evidence only.
