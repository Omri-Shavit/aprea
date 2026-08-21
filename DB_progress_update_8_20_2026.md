# DDR Evidence Matrix — progress update

**Date:** 20 August 2026
**Prepared by:** Omri Shavit
**Covers:** Julie's 6 August program brief and the 12 August expansion request from Julie and Oren

---

## 1. Summary

The database has been rebuilt from a WEE1-only mockup into a **DDR-wide evidence
matrix**, and the dummy data is gone. Every row now traces to a real
ClinicalTrials.gov record, a PubMed/Europe PMC identifier, or a measured GDSC
value.

| | Before (6 Aug) | Now |
|---|---|---|
| Targets | WEE1 only | 15 DDR targets |
| Evidence rows | ~40 synthetic | **50,186 real** |
| Drug dictionary | none | **84 agents** |
| Data source | invented | ClinicalTrials.gov, PubMed/Europe PMC, GDSC, Cell Model Passports |
| Confidential flag | present | removed — everything is public |

The three things Oren asked for on 12 August are built and working: **target-first
dropdowns that cascade into that target's drugs**, **all cancer types**, and a
**mono / combination therapy switch** with the four regimen tracks from the
brief kept as separate, filterable tracks.

**The most important caveat, stated up front:** this is now a genuine *evidence
map*, but it is **not yet a validated biomarker shortlist**. Section 5 explains
exactly which parts are measured findings and which are only inventory. I would
not want the ranking screen read as a recommendation in its current state.

---

## 2. What was built for the 12 August request

**Target → Drug cascade.** The Explorer opens on a Target selector covering all
15 DDR targets. Choosing one narrows the Drug dropdown to only that target's
agents, and target family is available as a third axis. The cascade is built
from the `(target, compound)` pairs actually present in the data, so it can
never offer a combination that returns nothing.

**All cancer types.** Indications are captured as recorded plus a normalised
broad category, so a user can filter by "gynecologic" without knowing every way
ovarian cancer is written. There are 2,457 distinct indication strings across 13
categories.

**Mono vs. combination.** A three-way All / Monotherapy / Combination control.
Selecting Combination reveals the regimen track and combination partner. The
brief's four analysis tracks are stored as first-class values, so each can be
analysed on its own:

| Track | Rows |
|---|---|
| Monotherapy | 39,192 |
| + targeted agent | 8,427 |
| + chemotherapy | 2,131 |
| + radiotherapy | 436 |

**Drug dictionary** (from step 1 of the 6 August brief). A new tab lists all 84
agents with aliases, developer, clinical stage, selectivity, dose, schedule and
known off-target activity. Aliases are what let a search for "AZD1775",
"MK-1775" or "adavosertib" find the same agent.

---

## 3. Where the data came from

| Layer | Source | Rows |
|---|---|---|
| Pharmacogenomic screening | GDSC (per-cell-line IC50/AUC), Cell Model Passports | 37,473 |
| Literature | PubMed / Europe PMC | 8,729 |
| Clinical registry | ClinicalTrials.gov API | 3,984 |

By evidence tier: 38,602 preclinical in vitro, 9,944 clinical, 986 preclinical in
vivo, 654 unclassified.

Coverage by target:

| Target | Rows | | Target | Rows |
|---|---|---|---|---|
| PARP | 23,638 | | USP1 | 1,036 |
| ATR | 6,040 | | DYRK1B | 992 |
| CHK1 | 5,514 | | DYRK1A | 820 |
| ATM | 4,294 | | PKMYT1 | 80 |
| WEE1 | 3,697 | | POLQ | 55 |
| DNA-PK | 2,268 | | CHK2 | 9 |
| multi-target | 1,736 | | APEX1 | 6 |
| | | | RAD51 | 1 |

The thin targets are thin because those agents genuinely have little registry or
GDSC presence, not because the harvest skipped them.

### Statistics that were actually computed

Mann-Whitney U on LN\_IC50 with Cohen's *d* and Benjamini-Hochberg correction:

- **1,179 lineage tests → 463 survive FDR < 0.1**
- **1,563 driver-mutation tests** across a 41-gene panel (genes mutated in ≥15 of
  974 sequenced models) **→ 103 survive**

These 566 results are the only rows in the database carrying a p-value, and each
one says so in its `notes` field. No clinical or literature row carries a
computed effect size.

---

## 4. Data-quality problems found and fixed

The pipeline ships with an audit (`ddr_scavenger/verify.py`, 30 checks, all
passing). It caught three defects that had produced real, wrong rows:

1. **An antibiotic was being counted as a cancer biomarker.** The pattern for
   Cyclin E1 matched case-insensitively against the end of "tetra**cycline**",
   "doxy**cycline**" and "mino**cycline**", tagging 258 microbiology papers —
   including a 1976 paper on *Yersinia* — as CCNE1 amplification evidence. Every
   biomarker pattern is now anchored at a word boundary. CCNE1 rows fell from 408
   to 88.
2. **The off-topic filter never ran.** It returned early whenever a compound was
   named, and every literature record names one by construction, so the check was
   dead code. This mattered because several dictionary entries are repurposed
   non-oncology molecules (novobiocin is an antibiotic, harmine an MAO
   inhibitor). Requiring an oncology context term removed 1,003 records; POLQ
   dropped from 283 rows to 55.
3. **A target the interface could not reach.** PARP7 was in the family map but
   missing from the list the API validates against, so its agent was
   unselectable. Rather than mislabel RBN-2397 as "PARP" — pooling an
   interferon-signalling agent with genuine synthetic-lethality inhibitors — it
   is excluded with a documented reason, and a build-time guard now prevents an
   unreachable value from recurring.

---

## 5. What this data is, and what it is not — please read

I would rather over-state these limits than have a number quoted onward that
does not deserve it.

**The 8,729 literature rows are uncurated keyword co-mentions.** A paper
mentioning both an agent and a biomarker produces a row. Nobody has read those
papers, and **no association is asserted** by their presence. Each row says so in
its `notes`.

**The 34,731 per-cell-line GDSC rows all carry `TP53 driver mutation` as their
biomarker.** That is a mutation annotation attached to a real measured IC50, not
an established TP53-response association.

**This distorts the current ranking.** "TP53 driver mutation" ranks first with
34,695 supporting rows, but that number is a count of cell lines carrying an
annotation, not 34,695 studies finding a TP53 effect. **The ranking screen today
reflects what has been measured most, not what is most promising.** It should not
be circulated as the ranked shortlist from step 4 of the brief.

**Nothing in the database currently supports a genuine predictive claim.**
`pct_randomized_interaction` is **0%**. Per the brief's own standard — a
biomarker is only predictive when a treatment-by-biomarker interaction is
demonstrated, ideally in randomized data — every association here is
hypothesis-generating. The schema records this explicitly per row via
`evidence_basis` (`randomized_interaction` / `single_arm_association` /
`responder_only` / `preclinical_correlation`), so the bar is visible rather than
assumed.

**Other limits:** 1,972 registry rows name no biomarker and use a documented
"none specified (unselected population)" placeholder; only 1,733 registry rows
had parseable posted results; `effect_size` and `p_value` are null on all 47,444
rows outside the computed-statistics set.

---

## 6. The eight scoring dimensions

Each biomarker is scored on the eight dimensions from the brief, and — this was a
deliberate choice — **each sub-score is shown individually** next to the
composite, so a reviewer can disagree with one dimension instead of with an
opaque number. Weights sit in one constant and can be re-tuned without touching
the maths.

| # | Dimension (brief) | Status |
|---|---|---|
| 1 | Strength of human clinical evidence | Working — from evidence tier, model type and study design |
| 2 | Reproducibility across datasets | Working — distinct contributing datasets |
| 3 | **Chemical vs. genetic concordance** | **No data — see below** |
| 4 | Mechanistic link to replication stress | Partial — curated pathway flags only |
| 5 | Prevalence in relevant populations | Proxy only — coverage, not true population prevalence |
| 6 | Distinguishing target benefit from partner benefit | Working — the four tracks make this comparable |
| 7 | Assay feasibility | Working — from assay modality and specimen type |
| 8 | Sample availability / validation feasibility | Working — from specimen type and timing |

**Dimension 3 is the significant gap.** All 50,186 rows are `chemical`
perturbation; there are **zero genetic rows**. The brief specifically asks
whether a biomarker predicts both drug sensitivity *and* CRISPR/RNAi dependency,
since agreement is what separates real target biology from compound-specific
off-target effects. The schema and scoring support this, but the DepMap CRISPR
gene-effect data has not been ingested, so this dimension currently scores 0 for
every biomarker. **This is the highest-value next data source**, and it is the
top item in section 8.

---

## 7. Engineering work behind the scenes

Loading real data at this scale surfaced problems the mockup never had.

**The Insights tab would have crashed the production container.** Each of its six
panels independently loaded all 50,186 rows, measured at **574 MB peak memory and
30.5 seconds**. The production container is provisioned with 512 MB, so this
would have been killed rather than slow. Two fixes: the aggregates now select
only the 25 columns they actually read instead of building full row objects, and
the six panels share one cached snapshot. Result: **185 MB and 1.1 seconds**, a
5× memory and 27× speed improvement. The cache is invalidated on every write, and
that invalidation is covered by tests plus an end-to-end check that adding and
deleting a row moves the totals immediately.

**Two display bugs that would have misled a reader.** Numbers were formatted to
three significant figures, which is right for an IC50 but meant an exact count of
**12,947 rendered as "12,900"**; counts now render exactly. Separately, a
null-versus-zero bug was making rows with no p-value appear as real data points
at the origin of the volcano plot and cells with no directional data render as
"0% sensitive" — both now correctly render as absent.

**Tests.** There were none; there are now 10, covering cache invalidation and the
contract between the aggregates and the query layer. I verified the guard fails
when the contract is broken, rather than assuming a passing test means anything.

---

## 8. Recommended next steps

1. **Ingest DepMap CRISPR gene-effect data** — unlocks scoring dimension 3, the
   one the brief singles out as separating WEE1 biology from off-target effects.
2. **Curate a defensible shortlist by hand.** The literature layer is a search
   index, not evidence. The realistic path to the "approximately five biomarkers"
   deliverable is human review of a filtered candidate set — the database now
   makes that filtering fast, but it cannot replace the reading.
3. **Decide how to treat the GDSC TP53 annotation** so it stops dominating the
   ranking by volume alone.
4. **Add the remaining pharmacogenomic sources** from the brief — PRISM, CTRP,
   PharmacoDB, NCI-60 — which would also make the reproducibility dimension
   meaningful, since it currently sees few independent datasets.
5. **Confirm the drug dictionary against your list.** You mentioned building one
   independently; comparing the two is the fastest way to find agents I missed.
6. **Authentication.** Login is disabled while everything is public. `@aprea.com`
   runs on Microsoft Entra ID, so this needs Entra rather than the Google sign-in
   originally built. Required before any confidential data is loaded.

---

## 9. Where things live

| What | Where |
|---|---|
| Web app | `wee1-evidence-app/frontend` → GitHub Pages |
| API | `wee1-evidence-app/backend` → Google Cloud Run |
| Database | Google Cloud SQL (PostgreSQL 15); SQLite locally |
| Harvest pipeline | `ddr_scavenger/` (`harvest_ddr.py`, `build_evidence.py`, `verify.py`) |
| Curated output | `backend/data/ddr_evidence.json`, `backend/data/ddr_compounds.json` |
| Field definitions | `DATA_DICTIONARY.md` |

Rebuilding from scratch is `harvest_ddr.py` → `build_evidence.py` → `verify.py` →
`ingest.py`. Every row records its own source, so any single number in the
interface can be traced back to the trial, paper or dataset it came from.
