import React, { useState } from "react";
import { api } from "../api";

// Minimal set of required + common fields. The API accepts the full schema;
// this form just demonstrates the write path (POST /api/evidence).
const REQUIRED = ["source_type", "compound", "indication", "model_type", "biomarker_name", "biomarker_type", "response_metric"];

const DEFAULTS = {
  source_type: "peer_reviewed",
  citation: "",
  compound: "adavosertib",
  alias: "",
  indication: "High-grade serous ovarian",
  model_type: "cell_line",
  biomarker_name: "",
  biomarker_type: "mutation",
  biomarker_status: "positive",
  response_metric: "IC50",
  response_value: "",
  units: "nM",
  direction: "sensitive",
  effect_size: "",
  p_value: "",
  predictive_vs_prognostic: "predictive",
  reproducibility: "single_dataset",
  wee1_specific_vs_combo: "wee1_specific",
  baseline_vs_pd: "baseline",
  evidence_tier: "preclinical_invitro",
  is_monotherapy: true,
  is_aprea_confidential: false,
  n: "",
};

const FIELDS = [
  ["source_type", "select", ["peer_reviewed", "abstract", "patent", "database", "internal_aprea"]],
  ["citation", "text"],
  ["compound", "text"],
  ["alias", "text"],
  ["indication", "text"],
  ["model_type", "select", ["cell_line", "xenograft", "pdx", "patient"]],
  ["biomarker_name", "text"],
  ["biomarker_type", "select", ["mutation", "cnv", "expression", "protein", "phospho", "signature"]],
  ["biomarker_status", "select", ["positive", "negative", "high", "low", "continuous"]],
  ["response_metric", "select", ["IC50", "AUC", "TGI", "ORR", "PFS", "DoR", "HR", "dependency"]],
  ["response_value", "number"],
  ["units", "text"],
  ["direction", "select", ["sensitive", "resistant", "neutral"]],
  ["effect_size", "number"],
  ["p_value", "number"],
  ["n", "number"],
  ["predictive_vs_prognostic", "select", ["predictive", "prognostic", "unclear"]],
  ["reproducibility", "select", ["single_dataset", "multi_dataset", "reproducible"]],
  ["wee1_specific_vs_combo", "select", ["wee1_specific", "combo_driven", "unclear"]],
  ["baseline_vs_pd", "select", ["baseline", "pharmacodynamic"]],
  ["evidence_tier", "select", ["preclinical_invitro", "preclinical_invivo", "clinical"]],
];

export default function AddEvidenceForm({ onClose, onCreated }) {
  const [form, setForm] = useState(DEFAULTS);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    for (const r of REQUIRED) {
      if (!form[r]) return setError(`"${r}" is required`);
    }
    setSaving(true);
    setError(null);
    // coerce numeric strings -> numbers / null
    const numeric = ["response_value", "effect_size", "p_value", "n"];
    const body = { ...form };
    numeric.forEach((k) => { body[k] = body[k] === "" ? null : Number(body[k]); });
    try {
      await api.createEvidence(body);
      onCreated();
    } catch (e) {
      setError(String(e));
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Add evidence row</h2>
        <p className="sub">Writes via <code>POST /api/evidence</code>. Required fields are marked *.</p>
        {error && <div className="tag resistant" style={{ display: "block", padding: "8px 12px", marginBottom: 12 }}>{error}</div>}
        <div className="form-grid">
          {FIELDS.map(([name, type, opts]) => (
            <div key={name}>
              <label>{name}{REQUIRED.includes(name) ? " *" : ""}</label>
              {type === "select" ? (
                <select value={form[name]} onChange={(e) => set(name, e.target.value)}>
                  {opts.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input type={type === "number" ? "number" : "text"} step="any"
                  value={form[name]} onChange={(e) => set(name, e.target.value)} />
              )}
            </div>
          ))}
          <div>
            <label>is_monotherapy</label>
            <input type="checkbox" checked={form.is_monotherapy} onChange={(e) => set("is_monotherapy", e.target.checked)} />
          </div>
          <div>
            <label>is_aprea_confidential</label>
            <input type="checkbox" checked={form.is_aprea_confidential} onChange={(e) => set("is_aprea_confidential", e.target.checked)} />
          </div>
        </div>
        <div className="modal-actions">
          <button className="btn secondary" onClick={onClose}>Cancel</button>
          <button className="btn" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Create row"}</button>
        </div>
      </div>
    </div>
  );
}
