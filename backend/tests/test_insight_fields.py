"""Guards the row contract between insights.py and main.py.

``main.py`` no longer hands insight functions whole ``Evidence`` objects; it
selects exactly the columns named in ``insights.INSIGHT_FIELDS``. If an insight
starts reading a field that is not in that tuple, the row simply will not have
the attribute and the endpoint raises ``AttributeError`` at request time. These
tests turn that into a failure here instead.

Both checks are needed, and each one catches what the other misses:

  * the static scan sees branches that a sample never executes - ``volcano``
    short-circuits on ``effect_size is None``, so a runtime probe over rows that
    all lack an effect size never evaluates ``r.p_value``;
  * the runtime probe sees dynamic access (``getattr(row, name)`` inside a
    lambda), which the static scan cannot resolve.
"""

from __future__ import annotations

import ast
from pathlib import Path

import insights as ins
from models import Evidence

INSIGHT_CALLS = (
    "summary",
    "composition",
    "biomarker_ranking",
    "indication_landscape",
    "volcano",
    "target_overview",
)


def test_declared_fields_exist_on_the_model():
    unknown = [f for f in ins.INSIGHT_FIELDS if f not in Evidence.model_fields]
    assert not unknown, f"INSIGHT_FIELDS names non-existent Evidence fields: {unknown}"


def test_no_field_is_read_without_being_declared_static():
    """Every ``<something>.<evidence_field>`` in insights.py must be declared."""
    source = Path(__file__).resolve().parent.parent / "insights.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    model_fields = set(Evidence.model_fields)

    referenced = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in model_fields
    }
    missing = sorted(referenced - set(ins.INSIGHT_FIELDS))
    assert not missing, (
        f"insights.py reads {missing} but does not declare it in INSIGHT_FIELDS, "
        f"so main.py will not select that column"
    )


def test_no_field_is_read_without_being_declared_at_runtime():
    """Run every insight over rows that expose *only* the declared fields.

    This is the same restriction the real query imposes, so anything read
    dynamically shows up as an AttributeError here.
    """
    declared = set(ins.INSIGHT_FIELDS)

    class StrictRow:
        """Exposes the declared fields and refuses everything else."""

        def __init__(self, **values):
            self.__dict__.update(values)

        def __getattr__(self, name):
            raise AssertionError(
                f"insight read undeclared field {name!r}; add it to INSIGHT_FIELDS"
            )

    # Two rows that between them exercise both sides of the null branches:
    # one fully populated, one with the optional numeric fields missing.
    populated = {
        "assay_modality": "ngs",
        "biomarker_name": "CCNE1 amplification",
        "biomarker_scope": "tumor_specific",
        "biomarker_type": "copy_number",
        "combination_track": "monotherapy",
        "compound": "adavosertib",
        "dataset_id": "NCT02272790",
        "direction": "sensitive",
        "effect_size": 1.4,
        "evidence_basis": "single_arm_association",
        "evidence_tier": "clinical",
        "id": 1,
        "indication": "ovarian cancer",
        "indication_category": "gynecologic",
        "is_monotherapy": True,
        "model_type": "patient",
        "n": 24,
        "p_value": 0.01,
        "perturbation_type": "chemical",
        "predictive_vs_prognostic": "predictive",
        "reproducibility": "single_dataset",
        "source_type": "peer_reviewed",
        "specimen_timing": "baseline",
        "specimen_type": "tumor_tissue",
        "target": "WEE1",
        "target_family": "checkpoint_kinase",
        "target_specific_vs_combo": "target_specific",
    }
    sparse = {**populated, "id": 2, "effect_size": None, "p_value": None,
              "direction": None, "n": None, "perturbation_type": "genetic"}

    assert set(populated) == declared, (
        "this test's fixture drifted from INSIGHT_FIELDS; update the fixture"
    )

    rows = [StrictRow(**populated), StrictRow(**sparse)]
    for name in INSIGHT_CALLS:
        getattr(ins, name)(rows)
    ins.indication_landscape(rows, by="target")


def test_insight_functions_tolerate_no_rows():
    for name in INSIGHT_CALLS:
        getattr(ins, name)([])
