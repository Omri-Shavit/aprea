import React, { useMemo, useState } from "react";
import { api } from "../api";
import { asArray, humanize } from "../format";

const REQUIRED = [
  "source_type",
  "target",
  "compound",
  "indication",
  "model_type",
  "biomarker_name",
  "biomarker_type",
  "response_metric",
];

const NUMERIC = ["response_value", "effect_size", "p_value", "n", "year"];

// Field types:
//   text / number      -> free input
//   combo              -> free input with vocab-backed suggestions (open vocabularies)
//   select             -> vocab options, falling back to the listed defaults
//   checkbox           -> boolean
// Grouped to mirror the evidence model the backend stores.
const SECTIONS = [
  [
    "Provenance",
    [
      ["source_type", "select", ["peer_reviewed", "abstract", "preprint", "patent", "database", "registry"]],
      ["citation", "text"],
      ["dataset_id", "text"],
      ["url_or_doi", "text"],
      ["year", "number"],
    ],
  ],
  [
    "Target & regimen",
    [
      ["target", "combo"],
      ["compound", "combo"],
      ["alias", "text"],
      ["is_monotherapy", "checkbox"],
      ["combination_track", "select", ["chemotherapy", "radiotherapy", "targeted_agent"]],
      ["combo_partner", "combo"],
      ["prior_therapies", "text"],
      ["treatment_setting", "select", ["monotherapy", "combination", "maintenance", "neoadjuvant", "adjuvant"]],
    ],
  ],
  [
    "Cancer type",
    [
      ["indication_category", "combo"],
      ["indication", "combo"],
    ],
  ],
  [
    "Model & specimen",
    [
      ["model_type", "select", ["cell_line", "organoid", "xenograft", "pdx", "patient"]],
      ["perturbation_type", "select", ["pharmacologic", "genetic_knockdown", "genetic_knockout", "overexpression"]],
      ["specimen_type", "select", ["cell_line", "tumor_tissue", "blood", "plasma", "pbmc", "xenograft_tissue"]],
      ["specimen_timing", "select", ["baseline", "on_treatment", "progression", "post_treatment"]],
    ],
  ],
  [
    "Biomarker",
    [
      ["biomarker_name", "combo"],
      ["biomarker_type", "select", ["mutation", "cnv", "expression", "protein", "phospho", "signature", "fusion"]],
      ["biomarker_scope", "select", ["single_gene", "pathway", "signature", "composite"]],
      ["biomarker_status", "select", ["positive", "negative", "high", "low", "continuous"]],
      ["assay_modality", "select", ["ngs", "rna_seq", "ihc", "western_blot", "flow_cytometry", "qpcr"]],
      ["baseline_vs_pd", "select", ["baseline", "pharmacodynamic"]],
    ],
  ],
  [
    "Outcome",
    [
      ["response_metric", "select", ["IC50", "AUC", "TGI", "ORR", "PFS", "OS", "DoR", "HR", "dependency"]],
      ["response_value", "number"],
      ["units", "combo"],
      ["direction", "select", ["sensitive", "resistant", "neutral"]],
      ["effect_size", "number"],
      ["p_value", "number"],
      ["n", "number"],
      ["endpoint_class", "select", ["preclinical_potency", "tumor_growth", "response_rate", "survival", "pharmacodynamic"]],
    ],
  ],
  [
    "Evidence quality",
    [
      ["evidence_tier", "select", ["preclinical_invitro", "preclinical_invivo", "clinical"]],
      ["evidence_basis", "select", ["in_vitro_screen", "in_vivo_study", "single_arm", "randomized", "retrospective", "case_series"]],
      ["predictive_vs_prognostic", "select", ["predictive", "prognostic", "unclear"]],
      ["target_specific_vs_combo", "select", ["target_specific", "combo_driven", "unclear"]],
      ["reproducibility", "select", ["single_dataset", "multi_dataset", "reproducible"]],
    ],
  ],
];

const ALL_FIELDS = SECTIONS.flatMap(([, fields]) => fields);
const COMBO_ONLY = ["combination_track", "combo_partner"];

// Field names that don't read well when mechanically title-cased.
const LABEL_OVERRIDES = {
  dataset_id: "Dataset ID",
  url_or_doi: "URL or DOI",
  is_monotherapy: "Monotherapy",
  baseline_vs_pd: "Baseline vs PD",
  predictive_vs_prognostic: "Predictive vs prognostic",
  target_specific_vs_combo: "Target-specific vs combo",
  p_value: "p-value",
  n: "n (sample size)",
  alias: "Compound alias",
};

function labelFor(name) {
  return LABEL_OVERRIDES[name] || humanize(name);
}

const DEFAULTS = Object.fromEntries(
  ALL_FIELDS.map(([name, type]) => [name, type === "checkbox" ? true : ""])
);

const UNIT_SUGGESTIONS = ["nM", "uM", "%", "months", "fold", "unitless"];

export default function AddEvidenceForm({ vocab, onClose, onCreated }) {
  const [form, setForm] = useState(DEFAULTS);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const compoundsForTarget = (t) => {
    const byTarget = vocab?.compounds_by_target;
    const all = asArray(vocab?.compound);
    if (!t) return all;
    if (byTarget && typeof byTarget === "object" && Object.keys(byTarget).length) {
      return asArray(byTarget[t]);
    }
    return all;
  };

  const compoundOptions = useMemo(
    () => compoundsForTarget(form.target),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [vocab, form.target]
  );

  // Switching the target drops a drug that is known to belong to another target,
  // but keeps a name the user typed by hand (it may be new to the dictionary).
  const onTargetChange = (next) => {
    setForm((f) => {
      const known = asArray(vocab?.compound).includes(f.compound);
      const allowed = compoundsForTarget(next);
      const invalid = known && !allowed.includes(f.compound);
      return { ...f, target: next, compound: invalid ? "" : f.compound };
    });
  };

  const optionsFor = (name, fallback) => {
    if (name === "compound") return compoundOptions;
    if (name === "units") {
      const v = asArray(vocab?.units);
      return v.length ? v : UNIT_SUGGESTIONS;
    }
    if (name === "combo_partner") {
      const byTrack = vocab?.combo_partners_by_track;
      if (form.combination_track && byTrack && typeof byTrack === "object") {
        const list = asArray(byTrack[form.combination_track]);
        if (list.length) return list;
      }
      return asArray(vocab?.combo_partner);
    }
    const fromVocab = asArray(vocab?.[name]);
    if (fromVocab.length) return fromVocab;
    // Server's canonical vocabulary (backend/vocabulary.py) before any local
    // fallback, so the form can offer every allowed value on an empty database
    // without the two lists drifting apart.
    const controlled = asArray(vocab?.controlled?.[name]);
    return controlled.length ? controlled : asArray(fallback);
  };

  const submit = async () => {
    for (const r of REQUIRED) {
      if (!String(form[r] ?? "").trim()) return setError(`"${labelFor(r)}" is required`);
    }
    setSaving(true);
    setError(null);
    const body = {};
    ALL_FIELDS.forEach(([name, type]) => {
      if (type === "checkbox") {
        body[name] = Boolean(form[name]);
        return;
      }
      const raw = typeof form[name] === "string" ? form[name].trim() : form[name];
      if (raw === "" || raw === undefined || raw === null) {
        body[name] = null;
        return;
      }
      body[name] = NUMERIC.includes(name) ? Number(raw) : raw;
    });
    if (body.is_monotherapy) {
      body.combination_track = null;
      body.combo_partner = null;
    }
    try {
      await api.createEvidence(body);
      onCreated();
    } catch (e) {
      setError(String(e));
      setSaving(false);
    }
  };

  const renderField = ([name, type, fallback]) => {
    if (type === "checkbox") {
      return (
        <div key={name} className="form-check">
          <label>{labelFor(name)}</label>
          <input
            type="checkbox"
            checked={Boolean(form[name])}
            onChange={(e) => set(name, e.target.checked)}
          />
        </div>
      );
    }
    const label = `${labelFor(name)}${REQUIRED.includes(name) ? " *" : ""}`;
    if (type === "select") {
      return (
        <div key={name}>
          <label>{label}</label>
          <select value={form[name] || ""} onChange={(e) => set(name, e.target.value)}>
            <option value="">—</option>
            {optionsFor(name, fallback).map((o) => (
              <option key={o} value={o}>
                {String(o)}
              </option>
            ))}
          </select>
        </div>
      );
    }
    if (type === "combo") {
      const listId = `vocab-${name}`;
      const options = name === "target" ? asArray(vocab?.target) : optionsFor(name, fallback);
      return (
        <div key={name}>
          <label>{label}</label>
          <input
            list={listId}
            value={form[name] || ""}
            onChange={(e) => (name === "target" ? onTargetChange(e.target.value) : set(name, e.target.value))}
          />
          <datalist id={listId}>
            {options.map((o) => (
              <option key={o} value={o} />
            ))}
          </datalist>
        </div>
      );
    }
    return (
      <div key={name}>
        <label>{label}</label>
        <input
          type={type === "number" ? "number" : "text"}
          step="any"
          value={form[name] || ""}
          onChange={(e) => set(name, e.target.value)}
        />
      </div>
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Add evidence row</h2>
        <p className="sub">
          Writes via <code>POST /api/evidence</code>. Required fields are marked *. Dropdown options
          come from the vocabularies already present in the database.
        </p>
        {error && (
          <div className="notice error" style={{ marginBottom: 12 }}>
            {error}
          </div>
        )}
        {SECTIONS.map(([section, fields]) => (
          <div className="form-section" key={section}>
            <div className="group-title">{section}</div>
            <div className="form-grid">
              {fields
                .filter(([name]) => !(form.is_monotherapy && COMBO_ONLY.includes(name)))
                .map(renderField)}
            </div>
          </div>
        ))}
        <div className="modal-actions">
          <button className="btn secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn" onClick={submit} disabled={saving}>
            {saving ? "Saving…" : "Create row"}
          </button>
        </div>
      </div>
    </div>
  );
}
