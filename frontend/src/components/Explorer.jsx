import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import AddEvidenceForm from "./AddEvidenceForm.jsx";

const FILTER_FIELDS = [
  ["compound", "Compound"],
  ["biomarker_name", "Biomarker"],
  ["biomarker_type", "Biomarker type"],
  ["indication", "Indication"],
  ["model_type", "Model type"],
  ["source_type", "Source type"],
  ["direction", "Direction"],
  ["treatment_setting", "Setting"],
  ["predictive_vs_prognostic", "Predictive / prognostic"],
  ["wee1_specific_vs_combo", "WEE1-specific / combo"],
  ["baseline_vs_pd", "Baseline / PD"],
  ["reproducibility", "Reproducibility"],
  ["evidence_tier", "Evidence tier"],
];

const COLUMNS = [
  ["compound", "Compound"],
  ["biomarker_name", "Biomarker"],
  ["indication", "Indication"],
  ["model_type", "Model"],
  ["direction", "Direction"],
  ["response_metric", "Metric"],
  ["response_value", "Value"],
  ["effect_size", "Effect"],
  ["p_value", "p"],
  ["predictive_vs_prognostic", "Class"],
  ["reproducibility", "Repro"],
  ["evidence_tier", "Tier"],
  ["n", "n"],
];

function Tag({ kind, value }) {
  if (!value) return <span className="tag muted">•</span>;
  const cls =
    kind === "direction"
      ? value
      : kind === "class"
      ? value === "predictive"
        ? "predictive"
        : value === "prognostic"
        ? "prognostic"
        : "muted"
      : "muted";
  return <span className={`tag ${cls}`}>{value}</span>;
}

export default function Explorer({ vocab, includeConfidential }) {
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState({});
  const [maxP, setMaxP] = useState("");
  const [monoOnly, setMonoOnly] = useState(false);
  const [sortBy, setSortBy] = useState("composite_relevance");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ total: 0, items: [] });
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const limit = 25;

  const params = useMemo(
    () => ({
      q,
      ...filters,
      max_p_value: maxP,
      is_monotherapy: monoOnly ? true : undefined,
      include_confidential: includeConfidential,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit,
      offset: page * limit,
    }),
    [q, filters, maxP, monoOnly, includeConfidential, sortBy, sortDir, page]
  );

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api
        .listEvidence(params)
        .then(setData)
        .catch(console.error)
        .finally(() => setLoading(false));
    }, 200); // debounce free-text search
    return () => clearTimeout(t);
  }, [params]);

  useEffect(() => setPage(0), [q, filters, maxP, monoOnly, includeConfidential]);

  const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v || undefined }));

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const clearAll = () => {
    setQ("");
    setFilters({});
    setMaxP("");
    setMonoOnly(false);
    setSortBy("composite_relevance");
  };

  const totalPages = Math.ceil(data.total / limit);

  return (
    <>
      <div className="panel">
        <h2>Search &amp; filter the evidence matrix</h2>
        <p className="sub">
          Free-text searches compound / alias / biomarker / indication / citation. Filters below map
          1:1 to the data-dictionary categorical fields.
        </p>

        <div className="search-row">
          <input
            className="search-input"
            placeholder="Search e.g. CCNE1, adavosertib, ovarian, azenosertib..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button className="btn" onClick={() => setShowAdd(true)}>+ Add evidence</button>
          <button className="btn secondary" onClick={clearAll}>Clear</button>
        </div>

        <div className="filters">
          {FILTER_FIELDS.map(([field, label]) => (
            <div className="filter" key={field}>
              <label>{label}</label>
              <select value={filters[field] || ""} onChange={(e) => setFilter(field, e.target.value)}>
                <option value="">Any</option>
                {(vocab?.[field] || []).map((v) => (
                  <option key={v} value={v}>{String(v)}</option>
                ))}
              </select>
            </div>
          ))}
          <div className="filter">
            <label>Max p-value</label>
            <input type="number" step="0.001" min="0" max="1" placeholder="e.g. 0.05"
              value={maxP} onChange={(e) => setMaxP(e.target.value)} />
          </div>
        </div>

        <div className="toggle-row">
          <label className="toggle">
            <span className="switch">
              <input type="checkbox" checked={monoOnly} onChange={(e) => setMonoOnly(e.target.checked)} />
              <span className="slider"></span>
            </span>
            Monotherapy only
          </label>
        </div>
      </div>

      <div className="panel">
        <div className="result-meta">
          <span>
            {loading ? "Loading…" : <><strong>{data.total}</strong> matching observations</>}
          </span>
          <span>Sorted by <strong>{sortBy}</strong> ({sortDir})</span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map(([col, label]) => (
                  <th key={col} onClick={() => toggleSort(col)}>
                    {label}{sortBy === col ? (sortDir === "desc" ? " ▾" : " ▴") : ""}
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.compound}
                    {r.is_aprea_confidential && <> <span className="tag confidential">Aprea</span></>}
                    {!r.is_monotherapy && <> <span className="tag muted">+{r.combo_partner}</span></>}
                  </td>
                  <td>{r.biomarker_name}</td>
                  <td>{r.indication}</td>
                  <td>{r.model_type}</td>
                  <td><Tag kind="direction" value={r.direction} /></td>
                  <td>{r.response_metric}</td>
                  <td>{r.response_value} {r.units !== "unitless" ? r.units : ""}</td>
                  <td>{r.effect_size}</td>
                  <td>{r.p_value}</td>
                  <td><Tag kind="class" value={r.predictive_vs_prognostic} /></td>
                  <td>{r.reproducibility}</td>
                  <td>{r.evidence_tier}</td>
                  <td>{r.n}</td>
                  <td>
                    <button className="btn danger" onClick={async () => {
                      const confirmed = window.confirm(
                        `Are you sure you want to delete this observation? ${r.compound} — ${r.biomarker_name} — ${r.indication} (${r.model_type})`
                      );
                      if (!confirmed) return;
                      await api.deleteEvidence(r.id);
                      setData((d) => ({ ...d, items: d.items.filter((x) => x.id !== r.id), total: d.total - 1 }));
                    }}>Delete</button>
                  </td>
                </tr>
              ))}
              {!loading && data.items.length === 0 && (
                <tr><td colSpan={COLUMNS.length + 1} className="loading">No rows match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <button className="page-btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            <span className="arrow">‹</span> Prev
          </button>
          <span>Page {page + 1} / {Math.max(totalPages, 1)}</span>
          <button className="page-btn next" disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next <span className="arrow">›</span>
          </button>
        </div>
      </div>

      {showAdd && (
        <AddEvidenceForm
          vocab={vocab}
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); setPage(0); setSortBy("id"); setSortDir("desc"); }}
        />
      )}
    </>
  );
}
