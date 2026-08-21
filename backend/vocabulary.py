"""Controlled vocabularies for the DDR evidence matrix.

Single source of truth for the categorical dimensions, shared by the API
(filter validation, dropdown ordering) and the ingestion pipeline. Display
order here is the order the UI renders; it is deliberately not alphabetical
(targets are grouped by how central they are to the program).
"""

# ---------------------------------------------------------------------------
# DDR targets, grouped into families
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

# Display order for the target dropdown.
TARGETS = [
    "WEE1",
    "ATR",
    "ATM",
    "CHK1",
    "CHK2",
    "DNA-PK",
    "PARP",
    "PKMYT1",
    "POLQ",
    "USP1",
    "DYRK1A",
    "DYRK1B",
    "RAD51",
    "APEX1",
    "multi",
]

TARGET_FAMILIES = [
    "checkpoint_kinase",
    "pikk",
    "parp_family",
    "polymerase",
    "deubiquitinase",
    "recombinase",
    "ber_enzyme",
    "kinase_other",
    "multi_target",
]

# ---------------------------------------------------------------------------
# Regimen: the four analysis tracks the brief requires be kept separate
# ---------------------------------------------------------------------------

COMBINATION_TRACKS = [
    "monotherapy",
    "chemotherapy",
    "radiotherapy",
    "targeted_agent",
]

# ---------------------------------------------------------------------------
# Cancer types
# ---------------------------------------------------------------------------

INDICATION_CATEGORIES = [
    "gynecologic",
    "thoracic",
    "gi",
    "breast",
    "gu",
    "head_neck",
    "cns",
    "sarcoma",
    "heme",
    "skin",
    "endocrine",
    "pan_cancer",
    "other",
]

# Maps a broad category to the specific indications seen in the sources. The
# ingestion pipeline uses this to assign indication_category; unmatched labels
# fall through to "other" rather than being dropped.
INDICATION_CATEGORY_MAP = {
    "gynecologic": [
        "ovarian", "fallopian", "peritoneal", "uterine", "endometrial", "cervical",
        "vulvar", "gynecolog", "leiomyosarcoma of uterus",
    ],
    "thoracic": [
        "lung", "nsclc", "sclc", "mesothelioma", "thymic", "thymoma", "bronch",
    ],
    "gi": [
        "colorectal", "colon", "rectal", "gastric", "stomach", "esophag", "pancrea",
        "hepatocellular", "liver", "biliary", "cholangio", "gallbladder", "anal",
        "gastrointestinal", "gist", "small bowel", "appendiceal",
    ],
    "breast": ["breast", "tnbc", "triple-negative", "triple negative"],
    "gu": [
        "prostate", "bladder", "urothelial", "renal", "kidney", "testicular",
        "germ cell", "penile", "ureter",
    ],
    "head_neck": [
        "head and neck", "hnscc", "oral", "oropharyn", "laryn", "nasopharyn",
        "salivary", "thyroid cancer", "sinonasal",
    ],
    "cns": [
        "glioma", "glioblastoma", "gbm", "medulloblastoma", "astrocytoma",
        "ependymoma", "dipg", "brain", "meningioma", "neuroblastoma", "cns",
    ],
    "sarcoma": [
        "sarcoma", "osteosarcoma", "ewing", "rhabdomyosarcoma", "liposarcoma",
        "leiomyosarcoma", "chondrosarcoma", "desmoid",
    ],
    "heme": [
        "leukemia", "leukaemia", "aml", "all", "cll", "cml", "lymphoma", "myeloma",
        "myelodysplastic", "mds", "hodgkin", "b-all", "t-all", "myelofibrosis",
    ],
    "skin": ["melanoma", "merkel", "cutaneous", "basal cell", "squamous cell skin"],
    "endocrine": ["adrenocortical", "pheochromocytoma", "neuroendocrine", "pituitary"],
    "pan_cancer": [
        "solid tumor", "solid tumour", "advanced solid", "pan-cancer", "pan cancer",
        "any solid", "multiple tumor", "unspecified", "cancer",
    ],
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

# Primary endpoint per the brief: objective response under RECIST (CR/PR).
PRIMARY_ENDPOINTS = ["ORR", "RECIST_response"]

# Secondary endpoints per the brief.
SECONDARY_ENDPOINTS = ["DoR", "PFS", "CBR_6mo", "ctDNA_reduction", "OS"]

PRECLINICAL_ENDPOINTS = ["IC50", "AUC", "GI50", "TGI", "dependency_score", "viability"]

RESPONSE_METRICS = PRIMARY_ENDPOINTS + SECONDARY_ENDPOINTS + PRECLINICAL_ENDPOINTS + ["HR"]

ENDPOINT_CLASSES = ["primary", "secondary", "exploratory", "preclinical"]


def endpoint_class_for(metric: str) -> str:
    """Classify a response metric into the brief's endpoint hierarchy."""
    if metric in PRIMARY_ENDPOINTS:
        return "primary"
    if metric in SECONDARY_ENDPOINTS:
        return "secondary"
    if metric in PRECLINICAL_ENDPOINTS:
        return "preclinical"
    return "exploratory"


# ---------------------------------------------------------------------------
# Remaining categorical dimensions
# ---------------------------------------------------------------------------

SOURCE_TYPES = ["peer_reviewed", "abstract", "patent", "database", "registry", "preprint"]
MODEL_TYPES = ["cell_line", "organoid", "xenograft", "pdx", "patient"]
PERTURBATION_TYPES = ["chemical", "genetic"]
BIOMARKER_TYPES = ["mutation", "cnv", "expression", "protein", "phospho", "signature", "fusion"]
BIOMARKER_SCOPES = ["tumor_specific", "tumor_agnostic"]
ASSAY_MODALITIES = ["ngs", "ihc", "rna", "liquid_biopsy", "proteomics", "functional"]
SPECIMEN_TYPES = [
    "tumor_tissue", "plasma_ctdna", "whole_blood", "pbmc", "skin_biopsy", "cell_pellet", "n/a",
]
SPECIMEN_TIMINGS = ["baseline", "on_treatment", "progression", "not_reported"]
DIRECTIONS = ["sensitive", "resistant", "neutral"]
EVIDENCE_TIERS = ["preclinical_invitro", "preclinical_invivo", "clinical"]
REPRODUCIBILITY = ["single_dataset", "multi_dataset", "reproducible"]
PREDICTIVE_CLASSES = ["predictive", "prognostic", "unclear"]
EVIDENCE_BASES = [
    "randomized_interaction",
    "single_arm_association",
    "responder_only",
    "preclinical_correlation",
]
ATTRIBUTION = ["target_specific", "combo_driven", "unclear"]
BASELINE_VS_PD = ["baseline", "pharmacodynamic"]
TREATMENT_SETTINGS = ["1st-line", "2nd-line+", "refractory", "maintenance", "n/a (preclinical)"]


def categorize_indication(indication: str) -> str:
    """Best-effort mapping of a free-text indication onto a broad category."""
    if not indication:
        return "other"
    text = indication.lower()
    # Check the specific categories before the pan-cancer catch-all, otherwise
    # "ovarian cancer" would match the bare word "cancer".
    for category, keywords in INDICATION_CATEGORY_MAP.items():
        if category == "pan_cancer":
            continue
        if any(k in text for k in keywords):
            return category
    if any(k in text for k in INDICATION_CATEGORY_MAP["pan_cancer"]):
        return "pan_cancer"
    return "other"
