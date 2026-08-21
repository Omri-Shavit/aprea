"""Shared vocabulary for the DDR (DNA damage response) evidence scavenger.

Generalises ``wee1_scavenger/wee1_config.py`` from WEE1 alone to the whole DDR target
space: WEE1, PKMYT1, ATR, ATM, CHK1, CHK2, DNA-PK, PARP, PARP7, POLQ, USP1,
DYRK1A/1B, RAD51 and APEX1.

Provenance of the compound dictionary
-------------------------------------
Every entry below was assembled from one of three checkable sources, recorded per
compound in ``source_of_record``:

  ``wee1_config``  carried over verbatim from the existing curated WEE1 dictionary at
                   ``wee1_scavenger/wee1_config.py``.
  ``gdsc``         the compound (and its TARGET annotation) appears in
                   ``cache/gdsc_screened_compounds.csv`` (GDSC release 8.5, 621 compounds).
                   ``gdsc_drug_ids`` gives the exact DRUG_IDs, so the annotation is
                   re-derivable from the CSV.
  ``registry``     the agent appears as an intervention on ClinicalTrials.gov; the
                   harvest confirms this and ``build_evidence.py`` overwrites
                   ``clinical_stage`` with the highest phase actually seen in the registry.

``clinical_stage`` here is a *curated prior*. It is deliberately superseded at build
time by the maximum phase observed in real ClinicalTrials.gov records, so the value
that reaches the database is registry-derived wherever a trial exists. Tool compounds
with no trials keep ``preclinical_tool``.

Fields left ``None`` are unknown. ``typical_dose``/``typical_schedule`` are intentionally
NOT populated here: dose is a property of a particular regimen, not of a molecule, so it
is carried on the Evidence rows where a real source stated it.

Deliberate exclusion pattern (inherited from wee1_config)
--------------------------------------------------------
A bare generic class string ("WEE1 inhibitor", "PARP inhibitor", "ATR inhibitor", ...)
must never be an alias of a specific compound. In the WEE1 harvest that mistake
mis-attributed ~357 records. ``GENERIC_CLASS_TERMS`` holds those strings, and an
import-time assertion fails the module if any of them leaks into an alias list.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Target -> family. Must agree with backend/vocabulary.py TARGET_FAMILY; build_evidence.py
# asserts the two are consistent rather than trusting this copy.
# ---------------------------------------------------------------------------
TARGET_FAMILY = {
    "WEE1": "checkpoint_kinase",
    "PKMYT1": "checkpoint_kinase",
    "CHK1": "checkpoint_kinase",
    "CHK2": "checkpoint_kinase",
    "ATR": "pikk",
    "ATM": "pikk",
    "DNA-PK": "pikk",
    "PARP": "parp_family",
    "PARP7": "parp_family",
    "POLQ": "polymerase",
    "POLA1": "polymerase",
    "USP1": "deubiquitinase",
    "DYRK1A": "kinase_other",
    "DYRK1B": "kinase_other",
    "RAD51": "recombinase",
    "APEX1": "ber_enzyme",
    "multi": "multi_target",
}

# ---------------------------------------------------------------------------
# Compound registry
# ---------------------------------------------------------------------------
# Keys per entry:
#   canonical            preferred (INN where one exists, else the development code)
#   aliases              every spelling seen in registries / literature / GDSC
#   target               primary DDR target, from the TARGET_FAMILY keys above
#   secondary_targets    other targets engaged at therapeutic concentrations, or None
#   developer            sponsor / originator
#   clinical_stage       curated prior; superseded by registry-observed max phase
#   selectivity          selectivity summary
#   off_target           off-target pharmacology relevant to interpreting results
#   chembl               ChEMBL id, or None when not verified
#   is_tool              True = preclinical probe, not a development candidate
#   gdsc_drug_ids        DRUG_IDs in gdsc_screened_compounds.csv (empty if absent)
#   source_of_record     see module docstring
#   no_text_match        True = too short/ambiguous to search literature text safely
#   notes                caveats
COMPOUNDS: list[dict] = [
    # =====================================================================
    # WEE1
    # =====================================================================
    {
        "canonical": "adavosertib",
        "aliases": ["adavosertib", "AZD1775", "AZD-1775", "AZD 1775", "MK-1775", "MK1775",
                    "MK 1775", "MK-1775 hemihydrate"],
        "target": "WEE1",
        "secondary_targets": "PLK1",
        "developer": "Merck & Co. / AstraZeneca",
        "clinical_stage": "phase_2",
        "selectivity": "WEE1-selective in biochemical assays; PLK1 inhibition emerges at higher "
                       "cellular concentrations.",
        "off_target": "PLK1. GDSC annotates drug 1179 as 'WEE1, PLK1'.",
        "chembl": "CHEMBL1976040",
        "is_tool": False,
        "gdsc_drug_ids": [1179],
        "source_of_record": "wee1_config + gdsc + registry",
        "notes": "Most-studied WEE1 inhibitor and the source of most clinical WEE1 evidence. "
                 "AstraZeneca largely deprioritised the programme; no approval.",
    },
    {
        "canonical": "azenosertib",
        "aliases": ["azenosertib", "ZN-c3", "ZNc3", "ZN c3", "KP-2638"],
        "target": "WEE1",
        "secondary_targets": None,
        "developer": "Zentalis Pharmaceuticals",
        "clinical_stage": "phase_2",
        "selectivity": "WEE1-selective; developed with a Cyclin E1 (CCNE1) patient-selection strategy.",
        "off_target": None,
        "chembl": "CHEMBL5314525",
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config + registry",
        "notes": None,
    },
    {
        "canonical": "Debio 0123",
        "aliases": ["Debio 0123", "Debio0123", "Debio-0123"],
        "target": "WEE1",
        "secondary_targets": None,
        "developer": "Debiopharm",
        "clinical_stage": "phase_1",
        "selectivity": "WEE1-selective; brain-penetrant.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config + registry",
        "notes": None,
    },
    {
        "canonical": "IMP7068",
        "aliases": ["IMP7068", "IMP-7068"],
        "target": "WEE1",
        "secondary_targets": None,
        "developer": "Impact Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config + registry",
        "notes": None,
    },
    {
        "canonical": "SY-4835",
        "aliases": ["SY-4835", "SY4835"],
        "target": "WEE1",
        "secondary_targets": None,
        "developer": "Shouyao Holdings",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config + registry",
        "notes": None,
    },
    {
        "canonical": "APR-1051",
        "aliases": ["APR-1051", "APR1051", "ATRN-W1051"],
        "target": "WEE1",
        "secondary_targets": None,
        "developer": "Aprea Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config + registry",
        "notes": "ACESOT-1051 first-in-human study. Public registry information only - no "
                 "Aprea-internal data is present anywhere in this database.",
    },
    {
        "canonical": "WJB001",
        "aliases": ["WJB001", "WJB-001"],
        "target": "WEE1",
        "secondary_targets": None,
        "developer": "Wigen Biomedicine Technology (Shanghai)",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config + registry",
        "notes": None,
    },
    {
        "canonical": "ACR-2316",
        "aliases": ["ACR-2316", "ACR2316"],
        "target": "WEE1",
        "secondary_targets": "PKMYT1",
        "developer": "Acrivon Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": "Designed as a dual WEE1/PKMYT1 inhibitor.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Dual WEE1/PKMYT1 mechanism is from the sponsor's public description; the "
                 "clinical_stage that reaches the database is registry-derived.",
    },
    {
        "canonical": "PD0166285",
        "aliases": ["PD0166285", "PD-0166285", "PD166285", "PD 166285"],
        "target": "WEE1",
        "secondary_targets": "PKMYT1; CHK1; Src-family kinases",
        "developer": "Pfizer (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Non-selective pyridopyrimidine: inhibits WEE1 and PKMYT1 (MYT1) with "
                       "additional tyrosine-kinase activity.",
        "off_target": "Src-family and other tyrosine kinases; interpret cellular phenotypes with care.",
        "chembl": "CHEMBL107792",
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config",
        "notes": None,
    },
    {
        "canonical": "PD407824",
        "aliases": ["PD407824", "PD-407824"],
        "target": "WEE1",
        "secondary_targets": "CHK1",
        "developer": "Tool compound (Pfizer series)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Dual WEE1/CHK1; not selective.",
        "off_target": None,
        "chembl": "CHEMBL198362",
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "wee1_config",
        "notes": None,
    },
    {
        # The bare string "Wee1 Inhibitor" is deliberately NOT an alias - see module docstring.
        "canonical": "WEE1 Inhibitor II (681640)",
        "aliases": ["Wee1 Inhibitor 681640", "WEE1 Inhibitor II", "681640"],
        "target": "WEE1",
        "secondary_targets": "CHK1",
        "developer": "Calbiochem / Merck (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1046 as 'WEE1, CHEK1' - dual activity.",
        "off_target": "CHK1.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1046],
        "source_of_record": "wee1_config + gdsc",
        "no_text_match": True,
        "notes": "'681640' alone is too generic a token for literature text matching, so this "
                 "compound is excluded from text search (GDSC data only).",
    },

    # =====================================================================
    # PKMYT1
    # =====================================================================
    {
        "canonical": "lunresertib",
        "aliases": ["lunresertib", "RP-6306", "RP6306", "RP 6306"],
        "target": "PKMYT1",
        "secondary_targets": None,
        "developer": "Repare Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": "First-in-class PKMYT1-selective inhibitor.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Developed with a CCNE1-amplification / FBXW7-mutation synthetic-lethal "
                 "selection hypothesis (MYTHIC programme).",
    },

    # =====================================================================
    # ATR
    # =====================================================================
    {
        "canonical": "ceralasertib",
        "aliases": ["ceralasertib", "AZD6738", "AZD-6738", "AZD 6738"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "AstraZeneca",
        "clinical_stage": "phase_3",
        "selectivity": "ATR-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [1394, 1917],
        "source_of_record": "gdsc + registry",
        "notes": "Most clinically advanced ATR inhibitor; extensively studied with durvalumab.",
    },
    {
        "canonical": "berzosertib",
        "aliases": ["berzosertib", "M6620", "M-6620", "VX-970", "VX970", "VX 970",
                    "VE-822", "VE822", "VE 822"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Vertex / Merck KGaA",
        "clinical_stage": "phase_2",
        "selectivity": "ATR-selective; intravenous.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [1613],
        "source_of_record": "gdsc + registry",
        "notes": "VE-822 / VX-970 / M6620 / berzosertib are the same molecule; GDSC drug 1613 is "
                 "listed as 'VE-822' with synonym 'Berzosertib'. Distinct from VE-821, the "
                 "earlier tool analogue (GDSC drug 2111).",
    },
    {
        "canonical": "elimusertib",
        "aliases": ["elimusertib", "BAY 1895344", "BAY1895344", "BAY-1895344"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Bayer",
        "clinical_stage": "phase_2",
        "selectivity": "ATR-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "camonsertib",
        "aliases": ["camonsertib", "RP-3500", "RP3500", "RP 3500", "RG6526"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Repare Therapeutics / Roche",
        "clinical_stage": "phase_2",
        "selectivity": "ATR-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "TRESR / ATTACC programme used a defined HRR/ATM-loss biomarker selection strategy.",
    },
    {
        "canonical": "gartisertib",
        "aliases": ["gartisertib", "M4344", "M-4344", "VX-803", "VX803"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Merck KGaA",
        "clinical_stage": "phase_1",
        "selectivity": "ATR-selective; oral.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "tuvusertib",
        "aliases": ["tuvusertib", "M1774", "M-1774"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Merck KGaA",
        "clinical_stage": "phase_1",
        "selectivity": "ATR-selective; oral.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "ART0380",
        "aliases": ["ART0380", "ART-0380", "ART 0380"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Artios Pharma",
        "clinical_stage": "phase_2",
        "selectivity": "ATR-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "ATRN-119",
        "aliases": ["ATRN-119", "ATRN119"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Aprea Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "ABOYA-119 first-in-human study. Public registry information only.",
    },
    {
        "canonical": "ATG-018",
        "aliases": ["ATG-018", "ATG018"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Antengene",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "IMP9064",
        "aliases": ["IMP9064", "IMP-9064"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Impact Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": None,
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "AZ20",
        "aliases": ["AZ20", "AZ-20"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "AstraZeneca (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "ATR-selective chemical probe; the lead series that produced ceralasertib.",
        "off_target": "mTOR at higher concentrations.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1184],
        "source_of_record": "gdsc",
        "notes": None,
    },
    {
        "canonical": "VE-821",
        "aliases": ["VE-821", "VE821", "VE 821"],
        "target": "ATR",
        "secondary_targets": None,
        "developer": "Vertex (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "ATR-selective chemical probe; ATM/DNA-PK activity only at much higher "
                       "concentrations.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [2111],
        "source_of_record": "gdsc",
        "notes": "Distinct compound from VE-822 (berzosertib) despite the near-identical code.",
    },

    # =====================================================================
    # ATM
    # =====================================================================
    {
        "canonical": "AZD0156",
        "aliases": ["AZD0156", "AZD-0156", "AZD 0156"],
        "target": "ATM",
        "secondary_targets": None,
        "developer": "AstraZeneca",
        "clinical_stage": "phase_1",
        "selectivity": "ATM-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "AZD1390",
        "aliases": ["AZD1390", "AZD-1390", "AZD 1390"],
        "target": "ATM",
        "secondary_targets": None,
        "developer": "AstraZeneca",
        "clinical_stage": "phase_1",
        "selectivity": "ATM-selective and brain-penetrant; developed as a radiosensitiser.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "M3541",
        "aliases": ["M3541", "M-3541"],
        "target": "ATM",
        "secondary_targets": None,
        "developer": "Merck KGaA",
        "clinical_stage": "phase_1",
        "selectivity": "ATM-selective radiosensitiser.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "KU-55933",
        "aliases": ["KU-55933", "KU55933", "KU 55933"],
        "target": "ATM",
        "secondary_targets": None,
        "developer": "KuDOS / AstraZeneca (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "The original ATM chemical probe; poor cellular potency and pharmacokinetics.",
        "off_target": "Reported activity on PI3K-family members and on glucose transport, "
                      "independent of ATM.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1030],
        "source_of_record": "gdsc",
        "notes": None,
    },
    {
        "canonical": "KU-60019",
        "aliases": ["KU-60019", "KU60019", "KU 60019"],
        "target": "ATM",
        "secondary_targets": None,
        "developer": "KuDOS / AstraZeneca (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Improved-potency ATM probe derived from KU-55933.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1185],
        "source_of_record": "gdsc",
        "notes": None,
    },
    {
        "canonical": "CP466722",
        "aliases": ["CP466722", "CP-466722", "CP 466722"],
        "target": "ATM",
        "secondary_targets": None,
        "developer": "Pfizer (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Rapid, reversible ATM probe.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [152],
        "source_of_record": "gdsc",
        "notes": None,
    },

    # =====================================================================
    # CHK1 / CHK2
    # =====================================================================
    {
        "canonical": "prexasertib",
        "aliases": ["prexasertib", "LY2606368", "LY-2606368", "LY 2606368", "ACR-368", "ACR368"],
        "target": "CHK1",
        "secondary_targets": "CHK2",
        "developer": "Eli Lilly; relicensed to Acrivon Therapeutics as ACR-368",
        "clinical_stage": "phase_2",
        "selectivity": "CHK1-selective with measurable CHK2 activity.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Acrivon is developing it with a proteomics-based (OncoSignature) patient-selection "
                 "assay rather than a single-gene biomarker.",
    },
    {
        "canonical": "rabusertib",
        "aliases": ["rabusertib", "LY2603618", "LY-2603618", "LY 2603618"],
        "target": "CHK1",
        "secondary_targets": None,
        "developer": "Eli Lilly",
        "clinical_stage": "phase_2",
        "selectivity": "CHK1-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Development discontinued after phase 2 combinations failed to improve outcomes.",
    },
    {
        "canonical": "SRA737",
        "aliases": ["SRA737", "SRA-737", "SRA 737", "CCT245737", "CCT-245737"],
        "target": "CHK1",
        "secondary_targets": None,
        "developer": "Cancer Research Technology / Sierra Oncology",
        "clinical_stage": "phase_2",
        "selectivity": "Oral CHK1-selective inhibitor.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Programme discontinued by the sponsor.",
    },
    {
        "canonical": "MK-8776",
        "aliases": ["MK-8776", "MK8776", "MK 8776", "SCH900776", "SCH-900776", "SCH 900776"],
        "target": "CHK1",
        "secondary_targets": "CHK2; CDK2",
        "developer": "Schering-Plough / Merck & Co.",
        "clinical_stage": "phase_1",
        "selectivity": "CHK1-selective; GDSC annotates drug 2046 as 'CHEK1, CHEK2, CDK2'.",
        "off_target": "CDK2 - relevant because CDK2 inhibition alone alters replication dynamics.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [2046],
        "source_of_record": "gdsc + registry",
        "notes": "Clinical development discontinued.",
    },
    {
        "canonical": "PF-477736",
        "aliases": ["PF-477736", "PF477736", "PF 477736"],
        "target": "CHK1",
        "secondary_targets": "CHK2",
        "developer": "Pfizer",
        "clinical_stage": "phase_1",
        "selectivity": "CHK1/CHK2.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Clinical development discontinued.",
    },
    {
        "canonical": "GDC-0575",
        "aliases": ["GDC-0575", "GDC0575", "ARRY-575", "ARRY575"],
        "target": "CHK1",
        "secondary_targets": None,
        "developer": "Array BioPharma / Genentech",
        "clinical_stage": "phase_1",
        "selectivity": "CHK1-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "BBI-355",
        "aliases": ["BBI-355", "BBI355"],
        "target": "CHK1",
        "secondary_targets": None,
        "developer": "Boundless Bio",
        "clinical_stage": "phase_1",
        "selectivity": "CHK1 inhibitor developed against extrachromosomal DNA (ecDNA)-driven tumours.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Selection hypothesis is ecDNA-based oncogene amplification, not a single mutation.",
    },
    {
        "canonical": "AZD7762",
        "aliases": ["AZD7762", "AZD-7762", "AZD 7762"],
        "target": "CHK1",
        "secondary_targets": "CHK2",
        "developer": "AstraZeneca",
        "clinical_stage": "phase_1",
        "selectivity": "Dual CHK1/CHK2; GDSC annotates drugs 1022 and 1402 as 'CHEK1, CHEK2'.",
        "off_target": "Reported activity on several other kinases; cardiac toxicity ended clinical "
                      "development, so it is now used mainly as a tool.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [1022, 1402],
        "source_of_record": "gdsc + registry",
        "notes": "Clinical development terminated for cardiotoxicity. Widely used preclinically, "
                 "but off-target activity limits target attribution.",
    },
    {
        "canonical": "FS106",
        "aliases": ["FS106", "FS-106"],
        "target": "CHK1",
        "secondary_targets": None,
        "developer": "GDSC screening collection",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1128 as CHEK1. Structure not disclosed in the release files.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1128],
        "source_of_record": "gdsc",
        "notes": "Screening-collection compound; identity known only from the GDSC annotation.",
    },
    {
        "canonical": "BML-277",
        "aliases": ["BML-277", "BML277", "CHK2 Inhibitor II"],
        "target": "CHK2",
        "secondary_targets": None,
        "developer": "Tool compound (commercial probe)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "CHK2-selective chemical probe.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": "Included so CHK2 is represented; there is no CHK2-selective clinical candidate. "
                 "No trials and no GDSC data, so this compound contributes dictionary coverage only.",
    },
    {
        "canonical": "PV1019",
        "aliases": ["PV1019", "PV-1019", "NSC 744039"],
        "target": "CHK2",
        "secondary_targets": None,
        "developer": "NCI (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "CHK2-selective chemical probe.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": "Dictionary coverage for CHK2 only; no trials, no GDSC data.",
    },

    # =====================================================================
    # DNA-PK
    # =====================================================================
    {
        "canonical": "peposertib",
        "aliases": ["peposertib", "nedisertib", "M3814", "M-3814", "MSC2490484A", "MSC-2490484A"],
        "target": "DNA-PK",
        "secondary_targets": None,
        "developer": "Merck KGaA",
        "clinical_stage": "phase_2",
        "selectivity": "DNA-PK-selective; developed as a radio- and chemo-sensitiser.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "'peposertib' and 'nedisertib' are both used for M3814 in the literature and "
                 "registries.",
    },
    {
        "canonical": "AZD7648",
        "aliases": ["AZD7648", "AZD-7648", "AZD 7648"],
        "target": "DNA-PK",
        "secondary_targets": None,
        "developer": "AstraZeneca",
        "clinical_stage": "phase_1",
        "selectivity": "DNA-PK-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "VX-984",
        "aliases": ["VX-984", "VX984", "M9831", "M-9831"],
        "target": "DNA-PK",
        "secondary_targets": None,
        "developer": "Vertex / Merck KGaA",
        "clinical_stage": "phase_1",
        "selectivity": "DNA-PK-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "NU7441",
        "aliases": ["NU7441", "NU-7441", "NU 7441", "KU-57788", "KU57788", "NU-7432", "NU-7741"],
        "target": "DNA-PK",
        "secondary_targets": None,
        "developer": "Newcastle University / KuDOS (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "The standard DNA-PK chemical probe.",
        "off_target": "PI3K-family activity at higher concentrations.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1038],
        "source_of_record": "gdsc",
        "notes": None,
    },
    {
        "canonical": "NU7026",
        "aliases": ["NU7026", "NU-7026", "NU 7026"],
        "target": "DNA-PK",
        "secondary_targets": None,
        "developer": "Newcastle University (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Early, lower-potency DNA-PK probe.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": None,
    },
    {
        "canonical": "CC-115",
        "aliases": ["CC-115", "CC115"],
        "target": "multi",
        "secondary_targets": "DNA-PK; mTOR (TORK)",
        "developer": "Celgene / Bristol Myers Squibb",
        "clinical_stage": "phase_1",
        "selectivity": "Dual DNA-PK / mTOR kinase inhibitor - by design not target-selective.",
        "off_target": "mTORC1/2 signalling confounds attribution of any effect to DNA-PK.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "voxtalisib",
        "aliases": ["voxtalisib", "XL-765", "XL765", "SAR245409", "SAR-245409"],
        "target": "multi",
        "secondary_targets": "PI3K (class I); DNA-PK; mTOR",
        "developer": "Exelixis / Sanofi",
        "clinical_stage": "phase_2",
        "selectivity": "GDSC annotates drug 375 as 'PI3K (class 1), DNAPK, MTOR'. PI3K/mTOR "
                       "activity dominates the cellular phenotype.",
        "off_target": "PI3K and mTOR. Not usable as evidence about DNA-PK biology on its own.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [375],
        "source_of_record": "gdsc + registry",
        "notes": None,
    },

    # =====================================================================
    # PARP
    # =====================================================================
    {
        "canonical": "olaparib",
        "aliases": ["olaparib", "AZD2281", "AZD-2281", "AZD 2281", "KU-0059436", "KU0059436",
                    "Lynparza"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "KuDOS / AstraZeneca / Merck & Co.",
        "clinical_stage": "approved",
        "selectivity": "PARP1/PARP2 dual inhibitor.",
        "off_target": None,
        "chembl": "CHEMBL521686",
        "is_tool": False,
        "gdsc_drug_ids": [1017, 1495],
        "source_of_record": "gdsc + registry",
        "notes": "Approved with BRCA1/2 and HRD companion diagnostics - the reference example of a "
                 "DDR agent with a validated selection biomarker.",
    },
    {
        "canonical": "niraparib",
        "aliases": ["niraparib", "MK-4827", "MK4827", "MK 4827", "Zejula"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "Merck & Co. / Tesaro / GSK",
        "clinical_stage": "approved",
        "selectivity": "PARP1/PARP2.",
        "off_target": None,
        "chembl": "CHEMBL1094636",
        "is_tool": False,
        "gdsc_drug_ids": [1177],
        "source_of_record": "gdsc + registry",
        "notes": None,
    },
    {
        "canonical": "rucaparib",
        "aliases": ["rucaparib", "AG-014699", "AG014699", "AG-14699", "AG-14447",
                    "PF-01367338", "PF01367338", "Rubraca"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "Agouron / Pfizer / Clovis Oncology",
        "clinical_stage": "approved",
        "selectivity": "PARP1/PARP2.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [1175],
        "source_of_record": "gdsc + registry",
        "notes": None,
    },
    {
        "canonical": "talazoparib",
        "aliases": ["talazoparib", "BMN-673", "BMN673", "BMN 673", "Talzenna"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "BioMarin / Medivation / Pfizer",
        "clinical_stage": "approved",
        "selectivity": "Most potent of the approved PARP1/2 inhibitors in cell-based assays.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [1259],
        "source_of_record": "gdsc + registry",
        "notes": "GDSC's synonym field lists 'BMN 973', which is a typographical variant of "
                 "BMN-673; it is not used as an alias here.",
    },
    {
        "canonical": "veliparib",
        "aliases": ["veliparib", "ABT-888", "ABT888", "ABT 888"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "Abbott / AbbVie",
        "clinical_stage": "phase_3",
        "selectivity": "PARP1/PARP2 catalytic inhibitor; a much weaker PARP trapper than olaparib "
                       "or talazoparib, which is the usual explanation for its weaker "
                       "single-agent activity.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [1018],
        "source_of_record": "gdsc + registry",
        "notes": "Phase 3 programmes did not lead to approval.",
    },
    {
        "canonical": "fluzoparib",
        "aliases": ["fluzoparib", "fuzuloparib", "SHR3162", "SHR-3162"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "Jiangsu HengRui Medicine",
        "clinical_stage": "approved",
        "selectivity": "PARP1/PARP2.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Approved in China.",
    },
    {
        "canonical": "pamiparib",
        "aliases": ["pamiparib", "BGB-290", "BGB290"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "BeiGene",
        "clinical_stage": "approved",
        "selectivity": "PARP1/PARP2; brain-penetrant.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Approved in China.",
    },
    {
        "canonical": "senaparib",
        "aliases": ["senaparib", "IMP4297", "IMP-4297"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2",
        "developer": "Impact Therapeutics / IMPACT Therapeutics",
        "clinical_stage": "phase_3",
        "selectivity": "PARP1/PARP2.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "saruparib",
        "aliases": ["saruparib", "AZD5305", "AZD-5305", "AZD 5305"],
        "target": "PARP",
        "secondary_targets": "PARP1 (selective over PARP2)",
        "developer": "AstraZeneca",
        "clinical_stage": "phase_3",
        "selectivity": "PARP1-selective and PARP1-trapping; designed to spare PARP2 and so reduce "
                       "haematological toxicity relative to PARP1/2 inhibitors.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Second-generation PARP1-selective class.",
    },
    {
        "canonical": "AZD9574",
        "aliases": ["AZD9574", "AZD-9574", "AZD 9574"],
        "target": "PARP",
        "secondary_targets": "PARP1 (selective over PARP2)",
        "developer": "AstraZeneca",
        "clinical_stage": "phase_2",
        "selectivity": "PARP1-selective and brain-penetrant.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "stenoparib",
        "aliases": ["stenoparib", "2X-121", "2X121", "E7449", "E-7449"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2; tankyrase 1/2 (PARP5a/PARP5b)",
        "developer": "Eisai / Allarity Therapeutics",
        "clinical_stage": "phase_2",
        "selectivity": "Dual PARP1/2 and tankyrase inhibitor - Wnt-pathway effects confound "
                       "attribution to PARP alone.",
        "off_target": "Tankyrase / Wnt signalling.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "iniparib",
        "aliases": ["iniparib", "BSI-201", "BSI201", "SAR240550"],
        "target": "PARP",
        "secondary_targets": None,
        "developer": "BiPar Sciences / Sanofi",
        "clinical_stage": "discontinued",
        "selectivity": "NOT a bona fide catalytic PARP inhibitor. Later work showed iniparib does "
                       "not inhibit PARP1 at clinically achieved exposures; its activity is "
                       "attributed to non-specific protein adduct formation.",
        "off_target": "Non-specific cysteine adduction.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Retained deliberately: iniparib's failed phase 3 is the standard cautionary "
                 "example of attributing a clinical result to a target the drug does not engage. "
                 "Do not pool iniparib evidence with real PARP inhibitor evidence.",
    },
    {
        "canonical": "RBN-2397",
        "aliases": ["RBN-2397", "RBN2397"],
        "target": "PARP7",
        "secondary_targets": None,
        "developer": "Ribon Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": "PARP7 (TIPARP)-selective mono-ADP-ribosyltransferase inhibitor - a "
                       "different mechanism from PARP1/2 inhibition (interferon signalling, not "
                       "synthetic lethality).",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Mechanistically distinct from PARP1/2 inhibitors; keep separate in any analysis.",
    },
    {
        "canonical": "PARP_9495",
        "aliases": ["PARP_9495"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2; PARP7",
        "developer": "GDSC screening collection (structure undisclosed)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1458 as 'PARP1, PARP2, PARP7'.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1458],
        "source_of_record": "gdsc",
        "no_text_match": True,
        "notes": "Anonymous GDSC screening code; usable as quantitative in vitro data only.",
    },
    {
        "canonical": "PARP_0108",
        "aliases": ["PARP_0108"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2; PARP6",
        "developer": "GDSC screening collection (structure undisclosed)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1459 as 'PARP1, PARP2, PARP6'.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1459],
        "source_of_record": "gdsc",
        "no_text_match": True,
        "notes": "Anonymous GDSC screening code; usable as quantitative in vitro data only.",
    },
    {
        "canonical": "PARP_9482",
        "aliases": ["PARP_9482"],
        "target": "PARP",
        "secondary_targets": "PARP1; PARP2; PARP5a (tankyrase 1)",
        "developer": "GDSC screening collection (structure undisclosed)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1460 as 'PARP1, PARP2, PARP5a'.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1460],
        "source_of_record": "gdsc",
        "no_text_match": True,
        "notes": "Anonymous GDSC screening code; usable as quantitative in vitro data only.",
    },
    {
        "canonical": "TANK_1366",
        "aliases": ["TANK_1366"],
        "target": "PARP",
        "secondary_targets": "tankyrase 1/2 (PARP5a/PARP5b)",
        "developer": "GDSC screening collection (structure undisclosed)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1461 as 'Tankyrase 1/2 (PARP5a, PARP5b)'. Tankyrases "
                       "are PARP-family enzymes but act on Wnt signalling and telomere "
                       "maintenance, not on the PARP1/2 synthetic-lethal axis.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1461],
        "source_of_record": "gdsc",
        "no_text_match": True,
        "notes": "Filed under the PARP family for schema reasons only. Do NOT pool with PARP1/2 "
                 "inhibitor evidence.",
    },

    # =====================================================================
    # POLQ (DNA polymerase theta)
    # =====================================================================
    {
        "canonical": "novobiocin",
        "aliases": ["novobiocin", "albamycin"],
        "target": "POLQ",
        "secondary_targets": "bacterial DNA gyrase (its original antibiotic target); HSP90",
        "developer": "Repurposed antibiotic (academic)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Binds the POLQ ATPase domain. A repurposed antibiotic, so it is far from "
                       "selective and its POLQ potency is low.",
        "off_target": "Bacterial gyrase, HSP90, and other targets - the least attributable POLQ "
                      "agent in this dictionary.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": None,
    },
    {
        "canonical": "ART558",
        "aliases": ["ART558", "ART-558"],
        "target": "POLQ",
        "secondary_targets": None,
        "developer": "Artios Pharma (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Selective inhibitor of the POLQ polymerase domain; the reference POLQ probe.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": None,
    },
    {
        "canonical": "ART4215",
        "aliases": ["ART4215", "ART-4215"],
        "target": "POLQ",
        "secondary_targets": None,
        "developer": "Artios Pharma",
        "clinical_stage": "phase_1",
        "selectivity": "POLQ-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "ART6043",
        "aliases": ["ART6043", "ART-6043"],
        "target": "POLQ",
        "secondary_targets": None,
        "developer": "Artios Pharma",
        "clinical_stage": "phase_1",
        "selectivity": "POLQ-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "GSK4524101",
        "aliases": ["GSK4524101", "GSK-4524101", "IDE705", "IDE-705"],
        "target": "POLQ",
        "secondary_targets": None,
        "developer": "IDEAYA Biosciences / GSK",
        "clinical_stage": "phase_1",
        "selectivity": "POLQ-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "The GSK4524101 / IDE705 identity comes from the partners' public naming; the "
                 "clinical_stage that reaches the database is registry-derived.",
    },

    # =====================================================================
    # USP1
    # =====================================================================
    {
        "canonical": "KSQ-4279",
        "aliases": ["KSQ-4279", "KSQ4279"],
        "target": "USP1",
        "secondary_targets": None,
        "developer": "KSQ Therapeutics / Roche",
        "clinical_stage": "phase_1",
        "selectivity": "USP1-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },
    {
        "canonical": "ISM3091",
        "aliases": ["ISM3091", "ISM-3091", "XL309", "XL-309"],
        "target": "USP1",
        "secondary_targets": None,
        "developer": "Insilico Medicine / Exelixis",
        "clinical_stage": "phase_1",
        "selectivity": "USP1-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "ISM3091 and XL309 are the same molecule under the two partners' codes. Listed "
                 "separately from KSQ-4279, which is a different compound.",
    },
    {
        "canonical": "TNG348",
        "aliases": ["TNG348", "TNG-348"],
        "target": "USP1",
        "secondary_targets": None,
        "developer": "Tango Therapeutics",
        "clinical_stage": "phase_1",
        "selectivity": "USP1-selective.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Development discontinued by the sponsor on liver-safety grounds.",
    },
    {
        "canonical": "ML323",
        "aliases": ["ML323", "ML-323"],
        "target": "USP1",
        "secondary_targets": "UAF1 (obligate USP1 partner)",
        "developer": "NIH Molecular Libraries probe",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Allosteric USP1/UAF1 inhibitor; GDSC annotates drug 1629 as 'USP1, UAF1'.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1629],
        "source_of_record": "gdsc",
        "notes": None,
    },

    # =====================================================================
    # DYRK1A / DYRK1B
    # =====================================================================
    {
        "canonical": "harmine",
        "aliases": ["harmine"],
        "target": "DYRK1A",
        "secondary_targets": "monoamine oxidase A (MAO-A)",
        "developer": "Natural product (beta-carboline)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "The classic DYRK1A probe, but it is a potent MAO-A inhibitor as well, so "
                       "cellular and in vivo effects cannot be attributed to DYRK1A.",
        "off_target": "MAO-A; other beta-carboline pharmacology.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": None,
    },
    {
        "canonical": "AZ191",
        "aliases": ["AZ191", "AZ-191"],
        "target": "DYRK1B",
        "secondary_targets": "DYRK1A",
        "developer": "AstraZeneca (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "DYRK1B-preferring probe with DYRK1A activity.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": None,
    },
    {
        "canonical": "EHT1610",
        "aliases": ["EHT1610", "EHT-1610", "EHT 1610"],
        "target": "DYRK1A",
        "secondary_targets": "DYRK1B",
        "developer": "ExonHit Therapeutics (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "DYRK1A/1B probe.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "notes": None,
    },
    {
        "canonical": "GSK626616AC",
        "aliases": ["GSK626616AC", "GSK-626616", "GSK626616"],
        "target": "DYRK1A",
        "secondary_targets": "DYRK3",
        "developer": "GlaxoSmithKline",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1779 as DYRK1A. Originally taken forward for anaemia, "
                       "not oncology.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1779],
        "source_of_record": "gdsc",
        "notes": None,
    },
    {
        "canonical": "Dyrk1b_0191",
        "aliases": ["Dyrk1b_0191"],
        "target": "DYRK1B",
        "secondary_targets": None,
        "developer": "GDSC screening collection (structure undisclosed)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1407 as DYRK1B.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1407],
        "source_of_record": "gdsc",
        "no_text_match": True,
        "notes": "Anonymous GDSC screening code; usable as quantitative in vitro data only.",
    },

    # =====================================================================
    # RAD51
    # =====================================================================
    {
        "canonical": "CYT-0851",
        "aliases": ["CYT-0851", "CYT0851"],
        "target": "RAD51",
        "secondary_targets": "MCT1 / MCT4 monocarboxylate transporters",
        "developer": "Cyteir Therapeutics",
        "clinical_stage": "phase_2",
        "selectivity": "Entered the clinic described as a RAD51 inhibitor; subsequent work "
                       "attributed its cellular activity to monocarboxylate-transporter "
                       "inhibition instead. Target attribution is genuinely unresolved.",
        "off_target": "MCT1/MCT4.",
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": "Treat as mechanism-uncertain. Do not use as evidence about RAD51 biology "
                 "without reading the primary mechanism papers.",
    },
    {
        "canonical": "B02",
        "aliases": ["RAD51 inhibitor B02"],
        "target": "RAD51",
        "secondary_targets": None,
        "developer": "Tool compound (academic)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Inhibits RAD51 DNA strand-exchange activity in vitro; requires high "
                       "micromolar concentrations in cells.",
        "off_target": None,
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "no_text_match": True,
        "notes": "The bare token 'B02' is far too ambiguous for literature text matching (it "
                 "collides with table and lane labels), so only the fully qualified phrase is an "
                 "alias and text search is disabled for this compound.",
    },
    {
        "canonical": "RI-1",
        "aliases": ["RAD51 inhibitor RI-1"],
        "target": "RAD51",
        "secondary_targets": None,
        "developer": "Tool compound (academic)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "Covalent RAD51 inhibitor probe.",
        "off_target": "Chloromaleimide reactivity implies additional covalent targets.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [],
        "source_of_record": "curated_probe_literature",
        "no_text_match": True,
        "notes": "'RI-1' is too ambiguous a token for text search; text matching disabled.",
    },

    # =====================================================================
    # APEX1
    # =====================================================================
    {
        "canonical": "APX3330",
        "aliases": ["APX3330", "APX-3330", "E3330", "E-3330"],
        "target": "APEX1",
        "secondary_targets": None,
        "developer": "Eisai / Apexian Pharmaceuticals",
        "clinical_stage": "phase_1",
        "selectivity": "Targets the APE1/Ref-1 redox function rather than its endonuclease "
                       "activity, so it is not a base-excision-repair inhibitor in the usual sense.",
        "off_target": None,
        "chembl": None,
        "is_tool": False,
        "gdsc_drug_ids": [],
        "source_of_record": "registry",
        "notes": None,
    },

    # =====================================================================
    # Multi-target DDR tools
    # =====================================================================
    {
        "canonical": "torin2",
        "aliases": ["torin2", "torin-2"],
        "target": "multi",
        "secondary_targets": "mTOR; ATM; ATR; DNA-PK",
        "developer": "Academic (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1202 as 'MTOR, ATM, ATR, DNAPK'. mTOR inhibition "
                       "dominates; not usable as single-target DDR evidence.",
        "off_target": "mTORC1/2.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1202],
        "source_of_record": "gdsc",
        "notes": None,
    },
    {
        "canonical": "QL-VIII-58",
        "aliases": ["QL-VIII-58", "QL VIII 58"],
        "target": "multi",
        "secondary_targets": "mTOR; ATR",
        "developer": "Academic (tool compound)",
        "clinical_stage": "preclinical_tool",
        "selectivity": "GDSC annotates drug 1166 as 'MTOR, ATR'.",
        "off_target": "mTORC1/2.",
        "chembl": None,
        "is_tool": True,
        "gdsc_drug_ids": [1166],
        "source_of_record": "gdsc",
        "notes": None,
    },
]

# ---------------------------------------------------------------------------
# Disambiguation-only entries: names that turn up alongside DDR agents in trials and
# papers but are NOT DDR-targeting agents. Kept out of ACTIVE_COMPOUNDS so they can
# never be matched as a DDR drug, but recorded so the reason is documented.
# ---------------------------------------------------------------------------
NOT_DDR_AGENTS = {
    "ZN-d5": "Zentalis BCL-2 inhibitor, co-listed in azenosertib combination trials.",
    "Mirin": "MRE11 nuclease inhibitor (GDSC drug 1048). A DDR tool, but MRE11 is outside the "
             "target vocabulary in backend/vocabulary.py, so it is excluded rather than "
             "mis-assigned to another target.",
    "FEN1_3940": "FEN1 inhibitor (GDSC drug 1419). FEN1 is outside the target vocabulary.",
    "Pyridostatin": "G-quadruplex stabiliser (GDSC 2044) - induces replication stress rather "
                    "than inhibiting a DDR target.",
    "KIN001-260": "CDC7 inhibitor (GDSC 290). CDC7 is a replication-initiation kinase outside "
                  "the target vocabulary.",
    "KIN001-266": "CDC7 inhibitor (GDSC 291).",
    "CRT0160829": "CDC7 inhibitor (GDSC 1183).",
    "Telomerase Inhibitor IX": "Telomerase inhibitor (GDSC 1930).",
    "BIBR-1532": "TERT inhibitor (GDSC 2043).",
    "RBN-2397": "PARP7 (TIPARP) inhibitor. Mechanistically distinct from PARP1/2 - it acts "
                "on interferon signalling, not synthetic lethality - and backend/vocabulary.py "
                "omits PARP7 from TARGETS, so its rows could not be reached by the target "
                "filter. Excluded rather than mislabelled 'PARP', which would pool it with "
                "genuine PARP1/2 inhibitor evidence.",
}

ACTIVE_COMPOUNDS = [c for c in COMPOUNDS if c["canonical"] not in NOT_DDR_AGENTS]

# ---------------------------------------------------------------------------
# Generic class strings. NEVER aliases of a specific compound.
# ---------------------------------------------------------------------------
GENERIC_CLASS_TERMS = [
    "WEE1 inhibitor", "WEE1 kinase inhibitor", "Wee-1 kinase inhibitor", "WEE1i", "anti-WEE1",
    "ATR inhibitor", "ATR kinase inhibitor", "ATRi",
    "ATM inhibitor", "ATM kinase inhibitor", "ATMi",
    "CHK1 inhibitor", "CHK2 inhibitor", "checkpoint kinase inhibitor", "CHK1i",
    "DNA-PK inhibitor", "DNA-PKcs inhibitor", "DNAPK inhibitor",
    "PARP inhibitor", "PARP1 inhibitor", "PARPi", "poly ADP-ribose polymerase inhibitor",
    "PKMYT1 inhibitor", "MYT1 inhibitor",
    "POLQ inhibitor", "polymerase theta inhibitor", "Pol-theta inhibitor",
    "USP1 inhibitor", "DYRK inhibitor", "DYRK1A inhibitor", "DYRK1B inhibitor",
    "RAD51 inhibitor", "DDR inhibitor", "DNA damage response inhibitor",
]

_generic_lower = {t.lower() for t in GENERIC_CLASS_TERMS}
for _c in ACTIVE_COMPOUNDS:
    for _a in _c["aliases"]:
        if _a.lower() in _generic_lower:
            raise AssertionError(
                f"{_c['canonical']}: generic class string {_a!r} must not be an alias. "
                "This is the exact mistake that mis-attributed ~357 records in the WEE1 harvest."
            )
    if _c["target"] not in TARGET_FAMILY:
        raise AssertionError(f"{_c['canonical']}: unknown target {_c['target']!r}")

_canon_names = [c["canonical"] for c in COMPOUNDS]
if len(_canon_names) != len(set(_canon_names)):
    raise AssertionError("duplicate canonical compound name in COMPOUNDS")


def _alias_pattern(alias: str) -> str:
    """Tolerant matcher: 'MK-1775' also matches 'MK 1775' / 'MK1775'."""
    core = re.escape(alias).replace(r"\-", r"[\-\s]?").replace(r"\ ", r"[\-\s]?")
    return rf"(?<![A-Za-z0-9]){core}(?![A-Za-z0-9])"


ALIAS_TO_CANONICAL: dict[str, str] = {}
for _c in ACTIVE_COMPOUNDS:
    for _a in _c["aliases"]:
        ALIAS_TO_CANONICAL[_a.lower()] = _c["canonical"]

BY_CANONICAL = {c["canonical"]: c for c in COMPOUNDS}

# Compounds safe to match against free text (excludes ambiguous short codes).
TEXT_MATCHABLE = [c for c in ACTIVE_COMPOUNDS if not c.get("no_text_match")]

ALIAS_REGEX = {
    c["canonical"]: re.compile("|".join(_alias_pattern(a) for a in c["aliases"]), re.I)
    for c in ACTIVE_COMPOUNDS
}
TEXT_ALIAS_REGEX = {c["canonical"]: ALIAS_REGEX[c["canonical"]] for c in TEXT_MATCHABLE}

GENERIC_REGEX = re.compile("|".join(_alias_pattern(t) for t in GENERIC_CLASS_TERMS), re.I)

GDSC_DRUG_ID_TO_CANONICAL: dict[int, str] = {}
for _c in COMPOUNDS:
    for _i in _c.get("gdsc_drug_ids", []):
        GDSC_DRUG_ID_TO_CANONICAL[_i] = _c["canonical"]

# Expected DRUG_NAME in gdsc_screened_compounds.csv for each id, so the harvester can
# assert the mapping still holds instead of trusting it.
GDSC_DRUG_ID_EXPECTED_NAME = {
    152: "CP466722", 375: "Voxtalisib", 1017: "Olaparib", 1018: "Veliparib", 1022: "AZD7762",
    1030: "KU-55933", 1038: "NU7441", 1046: "Wee1 Inhibitor", 1128: "FS106", 1166: "QL-VIII-58",
    1175: "Rucaparib", 1177: "Niraparib", 1179: "MK-1775", 1184: "AZ20", 1185: "KU-60019",
    1202: "torin2", 1259: "Talazoparib", 1394: "AZD6738", 1402: "AZD7762", 1407: "Dyrk1b_0191",
    1458: "PARP_9495", 1459: "PARP_0108", 1460: "PARP_9482", 1461: "TANK_1366", 1495: "Olaparib",
    1613: "VE-822", 1629: "ML323", 1779: "GSK626616AC", 1917: "AZD6738", 2046: "MK-8776",
    2111: "VE821",
}


def find_compounds(*texts, text_mode: bool = False) -> list[str]:
    """Return canonical DDR agent names mentioned in the supplied text blobs.

    ``text_mode=True`` restricts matching to compounds whose codes are unambiguous
    enough for free-text search (see ``no_text_match``).
    """
    blob = " ".join(t for t in texts if t)
    if not blob:
        return []
    rx = TEXT_ALIAS_REGEX if text_mode else ALIAS_REGEX
    return [canon for canon, r in rx.items() if r.search(blob)]


def mentions_generic_ddri(*texts) -> bool:
    blob = " ".join(t for t in texts if t)
    return bool(blob) and bool(GENERIC_REGEX.search(blob))


# ---------------------------------------------------------------------------
# Biomarker vocabulary
# ---------------------------------------------------------------------------
# Deliberately narrower than wee1_config.BIOMARKERS: the drug-class "context" entries
# there ("PARP inhibitor context", "ATR / ATM pathway") fire on every trial of the
# corresponding class and carry no biomarker information. Only molecular features,
# genuine functional signatures and pharmacodynamic markers are kept.
#
# Each entry: name -> (regex list, biomarker_type, scope)
BIOMARKERS: dict[str, tuple[list[str], str, str]] = {
    "TP53 mutation": ([r"\bTP53\b", r"\bp53\b(?!\s*binding)"], "mutation", "tumor_agnostic"),
    "CCNE1 amplification / Cyclin E1 high": (
        [r"\bCCNE1\b", r"cyclin[\-\s]?E1\b", r"cyclin[\-\s]?E\b"], "cnv", "tumor_agnostic"),
    "MYC / MYCN amplification": ([r"\bMYCN\b", r"\bMYC\b", r"\bc-?Myc\b"], "cnv", "tumor_agnostic"),
    "BRCA1/2 mutation": ([r"\bBRCA1\b", r"\bBRCA2\b", r"\bBRCA1/2\b", r"\bgBRCA\b", r"\bBRCAm\b"],
                         "mutation", "tumor_agnostic"),
    "Homologous recombination deficiency (HRD)": (
        [r"homologous recombination deficien", r"\bHRD\b", r"HR[\-\s]deficien",
         r"homologous recombination repair deficien", r"\bHRRm\b"], "signature", "tumor_agnostic"),
    "HRR gene alteration (non-BRCA)": (
        [r"\bPALB2\b", r"\bRAD51C\b", r"\bRAD51D\b", r"\bBARD1\b", r"\bBRIP1\b", r"\bCHEK2\b",
         r"\bFANCA\b", r"\bRAD54L\b", r"\bNBN\b"], "mutation", "tumor_agnostic"),
    "ATM loss / mutation": ([r"\bATM\b[\-\s]?(?:loss|deficien|mutat|altered|low)",
                             r"(?:loss|deficien\w*|mutation|alteration)s? (?:of|in) ATM\b",
                             r"\bATM[\-\s]deficient\b"], "mutation", "tumor_agnostic"),
    "ARID1A loss": ([r"\bARID1A\b"], "mutation", "tumor_agnostic"),
    "SLFN11 expression": ([r"\bSLFN11\b", r"\bSchlafen[\-\s]?11\b"], "expression", "tumor_agnostic"),
    "KRAS mutation": ([r"\bKRAS\b"], "mutation", "tumor_agnostic"),
    "FBXW7 mutation": ([r"\bFBXW7\b"], "mutation", "tumor_agnostic"),
    "PPP2R1A mutation": ([r"\bPPP2R1A\b"], "mutation", "tumor_agnostic"),
    "SETD2 loss": ([r"\bSETD2\b"], "mutation", "tumor_agnostic"),
    "RB1 loss": ([r"\bRB1\b", r"\bretinoblastoma (?:protein|gene) loss\b"], "cnv", "tumor_agnostic"),
    "PTEN loss": ([r"\bPTEN\b"], "cnv", "tumor_agnostic"),
    "CDKN2A loss": ([r"\bCDKN2A\b", r"\bp16 (?:loss|deletion)\b"], "cnv", "tumor_agnostic"),
    "MTAP deletion": ([r"\bMTAP\b"], "cnv", "tumor_agnostic"),
    "POLE / POLD1 mutation": ([r"\bPOLE\b", r"\bPOLD1\b"], "mutation", "tumor_agnostic"),
    "Mismatch repair deficiency / MSI": (
        [r"\bMSI-?H?\b", r"microsatellite instab", r"mismatch repair deficien", r"\bdMMR\b",
         r"\bMLH1\b", r"\bMSH2\b", r"\bMSH6\b", r"\bPMS2\b"], "signature", "tumor_agnostic"),
    "CDK12 alteration": ([r"\bCDK12\b"], "mutation", "tumor_agnostic"),
    "STK11 / LKB1 loss": ([r"\bSTK11\b", r"\bLKB1\b"], "mutation", "tumor_agnostic"),
    "SMARCA4 loss": ([r"\bSMARCA4\b", r"\bBRG1\b"], "mutation", "tumor_agnostic"),
    "PKMYT1 / MYT1 expression": ([r"\bPKMYT1\b", r"\bMYT1\b"], "expression", "tumor_agnostic"),
    "USP1 expression": ([r"\bUSP1\b"], "expression", "tumor_agnostic"),
    "FAM122A loss": ([r"\bFAM122A\b"], "expression", "tumor_agnostic"),
    "ERCC1 expression": ([r"\bERCC1\b"], "expression", "tumor_agnostic"),
    "53BP1 loss": ([r"\b53BP1\b", r"\bTP53BP1\b"], "expression", "tumor_agnostic"),
    "BRCA reversion mutation": ([r"reversion mutation", r"BRCA revers"], "mutation", "tumor_agnostic"),
    "Replication stress signature": (
        [r"replicat\w+ stress", r"fork collapse", r"origin firing", r"fork protection"],
        "signature", "tumor_agnostic"),
    "Tumor mutational burden": ([r"\bTMB\b", r"tumou?r mutational burden"], "signature",
                                "tumor_agnostic"),
    "Platinum resistance / sensitivity": (
        [r"platinum[\-\s]resistan", r"platinum[\-\s]refractor", r"platinum[\-\s]sensitiv"],
        "signature", "tumor_agnostic"),
    "pCDK1 Y15 (pharmacodynamic)": (
        [r"pCDK1", r"phospho[\-\s]?CDK1", r"\bTyr15\b", r"\bY15\b", r"pTyr15", r"pCDC2"],
        "phospho", "tumor_agnostic"),
    "gammaH2AX (pharmacodynamic)": (
        [r"\bH2AX\b", r"γH2AX", r"gamma[\-\s]?H2AX", r"g[\-\s]?H2AX"], "phospho", "tumor_agnostic"),
    "pCHK1 S345 (pharmacodynamic)": (
        [r"pCHK1", r"phospho[\-\s]?CHK1", r"\bSer345\b", r"\bS345\b"], "phospho", "tumor_agnostic"),
    "pRPA32 / pATR (pharmacodynamic)": (
        [r"\bpRPA(?:32|2)?\b", r"phospho[\-\s]?RPA", r"\bpATR\b", r"phospho[\-\s]?ATR"],
        "phospho", "tumor_agnostic"),
    "pDNA-PKcs S2056 (pharmacodynamic)": (
        [r"pDNA[\-\s]?PKcs", r"phospho[\-\s]?DNA[\-\s]?PK", r"\bS2056\b"], "phospho",
        "tumor_agnostic"),
    "PAR / PARylation (pharmacodynamic)": (
        [r"\bPARylation\b", r"poly\(ADP-ribose\)", r"\bPAR levels?\b"], "protein",
        "tumor_agnostic"),
}

def _anchor(pat: str) -> str:
    """Require a word boundary before any alternative that starts with a word character.

    Matching is case-insensitive, so an unanchored alternative can match the *tail* of a
    longer word. ``cyclin[\\-\\s]?E\\b`` matched the "cycline" in tetracycline,
    doxycycline and minocycline, which tagged 258 antibiotic-microbiology papers as
    CCNE1 evidence (novobiocin, a repurposed antibiotic, was the worst affected).
    Anchoring here rather than in each pattern keeps the whole dict safe by construction.
    """
    return rf"\b{pat}" if re.match(r"[A-Za-z0-9]", pat) else pat


BIOMARKER_REGEX = {k: re.compile("|".join(_anchor(p) for p in v[0]), re.I)
                   for k, v in BIOMARKERS.items()}
BIOMARKER_TYPE = {k: v[1] for k, v in BIOMARKERS.items()}
BIOMARKER_SCOPE = {k: v[2] for k, v in BIOMARKERS.items()}

# Placeholder used when a source names no biomarker at all. Documented and consistent,
# so these rows can be filtered out in one query.
NO_BIOMARKER_TRIAL = "none specified (unselected population)"
NO_BIOMARKER_CELL_LINE = "not characterised (no WES in Cell Model Passports)"


def find_biomarkers(*texts) -> list[str]:
    blob = " ".join(t for t in texts if t)
    if not blob:
        return []
    return [name for name, rx in BIOMARKER_REGEX.items() if rx.search(blob)]


# ---------------------------------------------------------------------------
# Combination-partner classification -> the four analysis tracks
# ---------------------------------------------------------------------------
# Precedence when a regimen spans several modalities: radiotherapy > chemotherapy >
# targeted_agent. Radiation is the defining modality of a chemoradiation regimen.
RADIO_RX = re.compile(
    r"\b(radiation|radiotherapy|radio[\-\s]?therapy|chemoradiation|chemoradiotherapy|"
    r"chemo[\-\s]?radi\w*|irradiat\w+|\bIMRT\b|\bSBRT\b|\bSRS\b|stereotactic|brachytherapy|"
    r"proton (?:beam|therapy)|external beam|whole[\-\s]brain radi|craniospinal|"
    r"radioembolizat\w+|radioligand|lutetium|Lu[\-\s]?177|radium[\-\s]?223|iodine[\-\s]?131|"
    r"I[\-\s]?131|yttrium[\-\s]?90|radioimmunotherapy)\b", re.I)

CHEMO_RX = re.compile(
    r"\b(cisplatin|carboplatin|oxaliplatin|nedaplatin|lobaplatin|platinum|"
    r"gemcitabine|gemzar|capecitabine|fluorouracil|5[\-\s]?FU\b|tegafur|S[\-\s]?1\b|"
    r"paclitaxel|nab[\-\s]?paclitaxel|abraxane|docetaxel|cabazitaxel|taxane|"
    r"irinotecan|liposomal irinotecan|nal[\-\s]?IRI|topotecan|\bSN[\-\s]?38\b|camptothecin|"
    r"etoposide|teniposide|doxorubicin|liposomal doxorubicin|doxil|caelyx|epirubicin|"
    r"daunorubicin|idarubicin|mitoxantrone|anthracycline|"
    r"temozolomide|dacarbazine|cyclophosphamide|ifosfamide|bendamustine|melphalan|busulfan|"
    r"carmustine|lomustine|chlorambucil|trabectedin|lurbinectedin|eribulin|"
    r"pemetrexed|methotrexate|pralatrexate|cytarabine|fludarabine|clofarabine|nelarabine|"
    r"cladribine|azacitidine|decitabine|hydroxyurea|mitomycin|bleomycin|"
    r"vincristine|vinblastine|vinorelbine|vindesine|actinomycin|dactinomycin|"
    r"chemotherapy|chemotherapeutic|\bFOLFOX\b|\bFOLFIRI\b|\bFOLFIRINOX\b|\bCHOP\b|"
    r"\bABVP?\b|\bEP\b regimen|\bICE\b regimen|\bDHAP\b|\bR[\-\s]?CHOP\b)\b", re.I)

# Interventions that are not therapy at all - never a combination partner.
NON_THERAPEUTIC_RX = re.compile(
    r"^\s*(placebo|matching placebo|saline|normal saline|vehicle|sham|no treatment|"
    r"best supportive care|observation|questionnaire\b.*|survey\b.*|blood (?:draw|sample|collection)|"
    r"biopsy|tumor biopsy|tissue collection|imaging|\bPET\b.*|\bCT\b scan.*|\bMRI\b.*|"
    r"ultrasound|biospecimen collection|laboratory biomarker analysis|"
    r"pharmacological study|pharmacokinetic\w* (?:study|sampling)|quality[\-\s]of[\-\s]life.*|"
    r"electrocardiogram|\bECG\b|physical examination|standard of care)\s*$", re.I)


def is_non_therapeutic(name: str) -> bool:
    return bool(NON_THERAPEUTIC_RX.match((name or "").strip()))


def classify_combination(partners: list[str]) -> tuple[str, str | None]:
    """Map a list of partner intervention names onto one of the four analysis tracks.

    Returns ``(combination_track, combo_partner_target)``. ``combo_partner_target``
    describes the partner's class, or None for monotherapy.
    """
    real = [p for p in partners if p and not is_non_therapeutic(p)]
    if not real:
        return "monotherapy", None
    blob = " ; ".join(real)
    if RADIO_RX.search(blob):
        return "radiotherapy", "radiation"
    if CHEMO_RX.search(blob):
        m = CHEMO_RX.search(blob)
        return "chemotherapy", (m.group(0).lower() if m else "cytotoxic chemotherapy")
    ddr = find_compounds(blob)
    if ddr:
        targets = sorted({BY_CANONICAL[d]["target"] for d in ddr if d in BY_CANONICAL})
        return "targeted_agent", "; ".join(targets) + " inhibitor"
    if IMMUNO_RX.search(blob):
        return "targeted_agent", "immune checkpoint inhibitor"
    return "targeted_agent", "other targeted agent"


IMMUNO_RX = re.compile(
    r"\b(pembrolizumab|nivolumab|durvalumab|atezolizumab|avelumab|ipilimumab|tremelimumab|"
    r"cemiplimab|dostarlimab|toripalimab|sintilimab|tislelizumab|camrelizumab|penpulimab|"
    r"serplulimab|retifanlimab|cosibelimab|anti[\-\s]?PD[\-\s]?[L]?1|anti[\-\s]?CTLA[\-\s]?4|"
    r"immune checkpoint|immunotherapy|interleukin[\-\s]?2|\bIL[\-\s]?2\b|vaccine|"
    r"CAR[\-\s]?T|bispecific)\b", re.I)


# ---------------------------------------------------------------------------
# Treatment setting (conservative; None when the source does not say)
# ---------------------------------------------------------------------------
FIRST_LINE_RX = re.compile(r"\b(first[\-\s]line|1st[\-\s]line|treatment[\-\s]na[iï]ve|"
                           r"previously untreated|newly diagnosed|no prior (?:systemic )?therapy)\b",
                           re.I)
LATER_LINE_RX = re.compile(r"\b(second[\-\s]line|2nd[\-\s]line|third[\-\s]line|previously treated|"
                           r"pretreated|pre[\-\s]treated|prior (?:systemic )?therap|relapsed|"
                           r"recurrent|progressed (?:on|after))\b", re.I)
REFRACTORY_RX = re.compile(r"\b(refractory|resistant to|platinum[\-\s]refractory)\b", re.I)
MAINTENANCE_RX = re.compile(r"\bmaintenance\b", re.I)


def treatment_setting_for(*texts) -> str | None:
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    if MAINTENANCE_RX.search(blob):
        return "maintenance"
    if REFRACTORY_RX.search(blob):
        return "refractory"
    if LATER_LINE_RX.search(blob):
        return "2nd-line+"
    if FIRST_LINE_RX.search(blob):
        return "1st-line"
    return None


# ---------------------------------------------------------------------------
# Evidence-type classification (carried over from wee1_config, unchanged behaviour)
# ---------------------------------------------------------------------------
CLINICAL_RX = re.compile(
    r"\b(patients?|phase[\s\-]?(?:0|1|2|3|i{1,3}|iv|1b|2a)|clinical trial|dose[\-\s]escalation|"
    r"first[\-\s]in[\-\s]human|recommended phase 2 dose|RP2D|maximum tolerated dose|\bMTD\b|"
    r"objective response rate|\bORR\b|progression[\-\s]free survival|overall survival|"
    r"cohort of patients)\b", re.I)
ANIMAL_RX = re.compile(
    r"\b(xenograft|PDX|patient[\-\s]derived xenograft|mouse|mice|murine|in vivo|"
    r"tumou?r growth inhibition|\bTGI\b|orthotopic|allograft|syngeneic|rat\b|zebrafish|"
    r"nude mice|NSG mice)\b", re.I)
INVITRO_RX = re.compile(
    r"\b(cell lines?|in vitro|IC50|GI50|EC50|clonogenic|organoids?|spheroids?|"
    r"cell viability|colony formation|CRISPR screen|siRNA|shRNA|MTT assay|CellTiter)\b", re.I)
REVIEW_RX = re.compile(r"\b(review|meta[\-\s]analysis|perspective|editorial|commentary)\b", re.I)


def classify_evidence(text: str, pub_types=None) -> str:
    """'+'-joined set of evidence tiers detected in the text; "" when nothing is detected."""
    pub_types = [p.lower() for p in (pub_types or [])]
    tiers = []
    if any("clinical trial" in p for p in pub_types) or CLINICAL_RX.search(text or ""):
        tiers.append("Clinical")
    if ANIMAL_RX.search(text or ""):
        tiers.append("In vivo (animal)")
    if INVITRO_RX.search(text or ""):
        tiers.append("In vitro")
    if not tiers:
        if any(p in ("review", "systematic review") for p in pub_types) or REVIEW_RX.search(text or ""):
            return "Review / narrative"
        return ""
    if any(p in ("review", "systematic review") for p in pub_types):
        tiers.append("Review")
    return " + ".join(tiers)


def evidence_tier_from_classification(label: str) -> str | None:
    """Map classify_evidence() output onto the schema's evidence_tier vocabulary."""
    if not label:
        return None
    if "Clinical" in label:
        return "clinical"
    if "In vivo" in label:
        return "preclinical_invivo"
    if "In vitro" in label:
        return "preclinical_invitro"
    return None


# ---------------------------------------------------------------------------
# Off-topic screen (WEE1/ATM/ATR are conserved genes: plant and yeast cell-cycle
# papers match the keyword without being drug research).
# ---------------------------------------------------------------------------
ONCOLOGY_RX = re.compile(
    r"\b(cancer|tumou?r|carcinom|sarcom|leukae?m|lymphom|glioma|glioblastom|melanom|myelom|"
    r"neoplas|malignan|metasta|oncolog|chemotherap|xenograft|patients?|cell lines?|"
    r"adenocarcinom|mesothelioma|neuroblastom|medulloblastom)", re.I)
NON_MAMMAL_RX = re.compile(
    r"\b(maize|Arabidopsis|plant|rice|wheat|tobacco|yeast|S\. cerevisiae|S\. pombe|"
    r"Schizosaccharomyces|Saccharomyces|Drosophila|C\. elegans|Xenopus|fission yeast|"
    r"budding yeast|seedling|root meristem)\b", re.I)


def off_topic_reason(text: str) -> str:
    """Flag a record as unlikely to be cancer drug research.

    Naming a dictionary compound is deliberately *not* enough to pass this screen.
    Several entries are repurposed non-oncology molecules - novobiocin is an antibiotic,
    harmine a monoamine-oxidase alkaloid - whose literature is dominated by their
    original field. Requiring an oncology term is what separates "novobiocin inhibits
    POLQ in BRCA-deficient tumours" from "novobiocin susceptibility of Yersinia
    enterocolitica". Callers should drop flagged records rather than annotate them.
    """
    body = text or ""
    if ONCOLOGY_RX.search(body):
        return ""
    if NON_MAMMAL_RX.search(body):
        return "OFF-TOPIC: non-mammalian DDR/cell-cycle biology, no oncology context."
    return "OFF-TOPIC: no oncology context (no cancer, tumour, patient or cell-line term)."


# ---------------------------------------------------------------------------
# Search-string builders
# ---------------------------------------------------------------------------
def ctgov_search_terms() -> list[str]:
    """One registry search term per compound (the canonical name plus its primary code).

    Also includes the generic class strings so trials that name only the class are
    retrieved - they are kept separate from named-compound trials downstream.
    """
    terms: list[str] = []
    for c in ACTIVE_COMPOUNDS:
        terms.append(c["canonical"])
        for a in c["aliases"][:3]:
            if a.lower() != c["canonical"].lower():
                terms.append(a)
    terms += ["WEE1 inhibitor", "ATR inhibitor", "ATM inhibitor", "DNA-PK inhibitor",
              "PARP inhibitor", "CHK1 inhibitor", "PKMYT1 inhibitor", "POLQ inhibitor",
              "USP1 inhibitor"]
    # Long anonymous GDSC codes have no registry presence; drop them to save requests.
    return sorted({t for t in terms if not re.match(r"^(PARP_|TANK_|Dyrk1b_|RAD51 inhibitor)", t)})


def pubmed_tiab_query(compound: dict) -> str:
    """PubMed query for one compound: any alias in title/abstract."""
    terms = sorted({f'"{a}"[tiab]' for a in compound["aliases"]})
    return "(" + " OR ".join(terms) + ")"


# Biomarker-context filter applied to the literature layer. Documented because it is a
# selection rule: without it the PARP inhibitor literature alone runs to tens of
# thousands of papers, almost none of which report a biomarker-response association.
PUBMED_BIOMARKER_FILTER = (
    '("TP53"[tiab] OR "p53"[tiab] OR "CCNE1"[tiab] OR "cyclin E"[tiab] OR "BRCA1"[tiab] OR '
    '"BRCA2"[tiab] OR "homologous recombination deficiency"[tiab] OR "HRD"[tiab] OR '
    '"SLFN11"[tiab] OR "ATM"[tiab] OR "ARID1A"[tiab] OR "KRAS"[tiab] OR "FBXW7"[tiab] OR '
    '"PPP2R1A"[tiab] OR "SETD2"[tiab] OR "RB1"[tiab] OR "PTEN"[tiab] OR "CDKN2A"[tiab] OR '
    '"MTAP"[tiab] OR "POLE"[tiab] OR "microsatellite instability"[tiab] OR "CDK12"[tiab] OR '
    '"STK11"[tiab] OR "SMARCA4"[tiab] OR "PKMYT1"[tiab] OR "USP1"[tiab] OR "FAM122A"[tiab] OR '
    '"ERCC1"[tiab] OR "53BP1"[tiab] OR "replication stress"[tiab] OR "H2AX"[tiab] OR '
    '"biomarker"[tiab] OR "predictive"[tiab] OR "sensitivity"[tiab] OR "resistance"[tiab] OR '
    '"synthetic lethal"[tiab] OR "synthetic lethality"[tiab])'
)

# ---------------------------------------------------------------------------
# Outcome-measure title -> controlled response_metric. Shared by the harvester (which
# parses posted results) and the builder (which reads declared endpoints), so the two
# can never drift apart. Ordered: the first pattern that matches wins.
# ---------------------------------------------------------------------------
OUTCOME_METRIC_PATTERNS: list[tuple[str, str]] = [
    (r"\b(objective response rate|overall response rate|\bORR\b|"
     r"percentage of (?:participants|patients) (?:with|achieving) (?:a )?(?:confirmed )?"
     r"(?:objective|overall|complete or partial) response|"
     r"(?:number|percentage) of (?:participants|patients) with (?:an )?objective response)\b",
     "ORR"),
    (r"\b(best overall response|objective response|overall response|"
     r"response rate (?:per|by|according to) RECIST|RECIST response|"
     r"(?:complete|partial) response rate|disease control rate)\b", "RECIST_response"),
    (r"\b(duration of response|\bDoR\b|\bDOR\b)\b", "DoR"),
    (r"\b(progression[\-\s]free survival|\bPFS\b)\b", "PFS"),
    (r"\b(overall survival|\bOS\b)\b", "OS"),
]
OUTCOME_METRIC_RX = [(re.compile(p, re.I), m) for p, m in OUTCOME_METRIC_PATTERNS]

# Ranking used when a trial reports several usable measures.
METRIC_RANK = {"ORR": 0, "RECIST_response": 1, "PFS": 2, "OS": 3, "DoR": 4}

# Recorded when a trial declares no efficacy endpoint at all (common for phase 1
# dose-escalation studies, whose primary endpoints are DLT / MTD / PK). Inventing "ORR"
# for those trials would be fabrication.
METRIC_NOT_REPORTED = "not_reported"


def map_outcome_metric(title: str) -> str | None:
    for rx, metric in OUTCOME_METRIC_RX:
        if rx.search(title or ""):
            return metric
    return None


NCBI_EMAIL = "ddr-evidence-scavenger@example.org"
USER_AGENT = "DDR-evidence-scavenger/1.0 (research; contact: data-team)"
