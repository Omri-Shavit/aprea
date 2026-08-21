import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { EMPTY, asArray, count, num, txt } from "../format";
import AddEvidenceForm from "./AddEvidenceForm.jsx";

// Secondary categorical filters, grouped so ~25 dropdowns stay navigable.
const FILTER_GROUPS = [
  [
    "Evidence quality",
    [
      ["evidence_tier", "Evidence tier"],
      ["evidence_basis", "Evidence basis"],
      ["reproducibility", "Reproducibility"],
      ["predictive_vs_prognostic", "Predictive / prognostic"],
      ["target_specific_vs_combo", "Target-specific / combo"],
      ["source_type", "Source type"],
    ],
  ],
  [
    "Biomarker",
    [
      ["biomarker_name", "Biomarker"],
      ["biomarker_type", "Biomarker type"],
      ["biomarker_scope", "Biomarker scope"],
      ["assay_modality", "Assay modality"],
      ["baseline_vs_pd", "Baseline / PD"],
    ],
  ],
  [
    "Model & specimen",
    [
      ["model_type", "Model type"],
      ["perturbation_type", "Perturbation"],
      ["specimen_type", "Specimen type"],
      ["specimen_timing", "Specimen timing"],
      ["treatment_setting", "Treatment setting"],
    ],
  ],
  [
    "Outcome",
    [
      ["response_metric", "Response metric"],
      ["endpoint_class", "Endpoint class"],
      ["direction", "Direction"],
    ],
  ],
];

const SECONDARY_FIELDS = FILTER_GROUPS.flatMap(([, fields]) => fields.map(([f]) => f));

const COLUMNS = [
  ["target", "Target"],
  ["compound", "Compound"],
  ["biomarker_name", "Biomarker"],
  ["indication", "Indication"],
  ["model_type", "Model"],
  ["perturbation_type", "Perturbation"],
  ["direction", "Direction"],
  ["response_metric", "Metric"],
  ["response_value", "Value"],
  ["effect_size", "Effect"],
  ["p_value", "p"],
  ["evidence_tier", "Tier"],
  ["n", "n"],
];

const THERAPY_MODES = [
  ["all", "All"],
  ["mono", "Monotherapy"],
  ["combo", "Combination"],
];

const LABELS = {
  q: "Search",
  target: "Target",
  target_family: "Target family",
  compound: "Drug",
  indication_category: "Cancer type",
  indication: "Specific indication",
  therapy_mode: "Therapy",
  combination_track: "Regimen track",
  combo_partner: "Combination partner",
  max_p_value: "Max p",
  min_year: "From year",
  ...Object.fromEntries(FILTER_GROUPS.flatMap(([, fields]) => fields)),
};

function Tag({ kind, value }) {
  if (!value) return <span className="muted-cell">{EMPTY}</span>;
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

function Cell({ value }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted-cell">{EMPTY}</span>;
  }
  return <>{String(value)}</>;
}

// Real rows carry NCT ids, PMIDs and GDSC dataset ids plus a URL or DOI — render
// the id as a link so every claim in the table is auditable in one click.
function SourceCell({ row }) {
  const label = row?.dataset_id || row?.citation || "";
  const raw = row?.url_or_doi || "";
  if (!label && !raw) return <span className="muted-cell">{EMPTY}</span>;
  const text = label || "source";
  if (!raw) return <span title={row?.citation || ""}>{text}</span>;
  const href = /^https?:\/\//i.test(raw) ? raw : `https://doi.org/${raw.replace(/^doi:\s*/i, "")}`;
  return (
    <a
      className="source-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={row?.citation || href}
    >
      {text}
    </a>
  );
}

function ValueCell({ row }) {
  const v = num(row?.response_value);
  if (v === EMPTY) return <span className="muted-cell">{EMPTY}</span>;
  const u = row?.units;
  const units = !u || u === "unitless" ? "" : u === "%" ? "%" : ` ${u}`;
  return (
    <>
      {v}
      {units}
    </>
  );
}

// Learn indication_category -> indication from rows as they stream in, so the
// specific-indication dropdown can be narrowed without an extra endpoint.
function mergeCategoryMap(prev, items) {
  let changed = false;
  const next = { ...prev };
  asArray(items).forEach((r) => {
    const cat = r?.indication_category;
    const ind = r?.indication;
    if (!cat || !ind) return;
    const list = next[cat] || [];
    if (!list.includes(ind)) {
      next[cat] = [...list, ind].sort();
      changed = true;
    }
  });
  return changed ? next : prev;
}

export default function Explorer({ vocab }) {
  const [q, setQ] = useState("");
  const [target, setTarget] = useState("");
  const [targetFamily, setTargetFamily] = useState("");
  const [compound, setCompound] = useState("");
  const [indicationCategory, setIndicationCategory] = useState("");
  const [indication, setIndication] = useState("");
  const [therapyMode, setTherapyMode] = useState("all");
  const [combinationTrack, setCombinationTrack] = useState("");
  const [comboPartner, setComboPartner] = useState("");
  const [filters, setFilters] = useState({});
  const [maxP, setMaxP] = useState("");
  const [minYear, setMinYear] = useState("");
  const [showMore, setShowMore] = useState(false);
  const [sortBy, setSortBy] = useState("composite_relevance");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ total: 0, items: [] });
  const [categoryMap, setCategoryMap] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const limit = 25;

  const compoundsForTarget = useCallback(
    (t) => {
      const byTarget = vocab?.compounds_by_target;
      const all = asArray(vocab?.compound);
      if (!t) return all;
      if (byTarget && typeof byTarget === "object" && Object.keys(byTarget).length) {
        return asArray(byTarget[t]);
      }
      return all;
    },
    [vocab]
  );

  const compoundOptions = useMemo(() => compoundsForTarget(target), [compoundsForTarget, target]);

  // Prefer values actually present in the data, so a filter never offers an option
  // that returns nothing. Closed vocabularies fall back to the server's canonical
  // list (backend/vocabulary.py) so the controls still work on an empty database.
  const optionsFor = useCallback(
    (field) => {
      const fromData = asArray(vocab?.[field]);
      if (fromData.length) return fromData;
      return asArray(vocab?.controlled?.[field]);
    },
    [vocab]
  );

  const narrowedIndications = indicationCategory ? asArray(categoryMap[indicationCategory]) : [];
  const indicationOptions = narrowedIndications.length
    ? narrowedIndications
    : asArray(vocab?.indication);

  const comboPartnerOptions = useMemo(() => {
    const byTrack = vocab?.combo_partners_by_track;
    if (combinationTrack && byTrack && typeof byTrack === "object") {
      const list = asArray(byTrack[combinationTrack]);
      if (list.length) return list;
    }
    return asArray(vocab?.combo_partner);
  }, [vocab, combinationTrack]);

  const params = useMemo(
    () => ({
      q,
      target: target || undefined,
      target_family: targetFamily || undefined,
      compound: compound || undefined,
      indication_category: indicationCategory || undefined,
      indication: indication || undefined,
      therapy_mode: therapyMode !== "all" ? therapyMode : undefined,
      combination_track: therapyMode === "combo" ? combinationTrack || undefined : undefined,
      combo_partner: therapyMode === "combo" ? comboPartner || undefined : undefined,
      ...filters,
      max_p_value: maxP || undefined,
      min_year: minYear || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit,
      offset: page * limit,
    }),
    [
      q,
      target,
      targetFamily,
      compound,
      indicationCategory,
      indication,
      therapyMode,
      combinationTrack,
      comboPartner,
      filters,
      maxP,
      minYear,
      sortBy,
      sortDir,
      page,
    ]
  );

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api
        .listEvidence(params)
        .then((res) => {
          const items = asArray(res?.items);
          setData({ total: Number(res?.total) || 0, items });
          setCategoryMap((prev) => mergeCategoryMap(prev, items));
          setError(null);
        })
        .catch((e) => {
          console.error(e);
          setError(String(e?.message || e));
          setData({ total: 0, items: [] });
        })
        .finally(() => setLoading(false));
    }, 200); // debounce free-text search
    return () => clearTimeout(t);
  }, [params]);

  useEffect(() => {
    setPage(0);
  }, [
    q,
    target,
    targetFamily,
    compound,
    indicationCategory,
    indication,
    therapyMode,
    combinationTrack,
    comboPartner,
    filters,
    maxP,
    minYear,
  ]);

  const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v || undefined }));

  // Changing the target invalidates a drug that belongs to another target.
  const onTargetChange = (next) => {
    setTarget(next);
    if (compound && !compoundsForTarget(next).includes(compound)) setCompound("");
  };

  const onCategoryChange = (next) => {
    setIndicationCategory(next);
    const known = asArray(categoryMap[next]);
    if (next && indication && known.length && !known.includes(indication)) setIndication("");
  };

  const onTrackChange = (next) => {
    setCombinationTrack(next);
    const byTrack = vocab?.combo_partners_by_track;
    const known = next && byTrack ? asArray(byTrack[next]) : [];
    if (comboPartner && known.length && !known.includes(comboPartner)) setComboPartner("");
  };

  const onTherapyModeChange = (mode) => {
    setTherapyMode(mode);
    if (mode !== "combo") {
      setCombinationTrack("");
      setComboPartner("");
    }
  };

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const clearAll = () => {
    setQ("");
    setTarget("");
    setTargetFamily("");
    setCompound("");
    setIndicationCategory("");
    setIndication("");
    setTherapyMode("all");
    setCombinationTrack("");
    setComboPartner("");
    setFilters({});
    setMaxP("");
    setMinYear("");
    setSortBy("composite_relevance");
    setSortDir("desc");
  };

  const activeChips = [];
  const chip = (key, value, onRemove) => {
    if (!value) return;
    activeChips.push({ key, label: LABELS[key] || key, value, onRemove });
  };
  chip("q", q, () => setQ(""));
  chip("target", target, () => onTargetChange(""));
  chip("target_family", targetFamily, () => setTargetFamily(""));
  chip("compound", compound, () => setCompound(""));
  chip("indication_category", indicationCategory, () => onCategoryChange(""));
  chip("indication", indication, () => setIndication(""));
  if (therapyMode !== "all") {
    chip(
      "therapy_mode",
      therapyMode === "mono" ? "monotherapy" : "combination",
      () => onTherapyModeChange("all")
    );
  }
  chip("combination_track", combinationTrack, () => onTrackChange(""));
  chip("combo_partner", comboPartner, () => setComboPartner(""));
  SECONDARY_FIELDS.forEach((f) => chip(f, filters[f], () => setFilter(f, "")));
  chip("max_p_value", maxP, () => setMaxP(""));
  chip("min_year", minYear, () => setMinYear(""));

  const secondaryActive = SECONDARY_FIELDS.filter((f) => filters[f]).length + (maxP ? 1 : 0) + (minYear ? 1 : 0);
  const items = asArray(data.items);
  const totalPages = Math.max(1, Math.ceil((Number(data.total) || 0) / limit));

  return (
    <>
      <div className="panel">
        <h2>Search &amp; filter the evidence matrix</h2>
        <p className="sub">
          Start with a DDR target, then pick one of that target&apos;s drugs. Every row links back
          to its source trial, dataset or publication.
        </p>

        <div className="primary-filters">
          <div className="filter filter-lg">
            <label>Target</label>
            <select value={target} onChange={(e) => onTargetChange(e.target.value)}>
              <option value="">All targets</option>
              {optionsFor("target").map((v) => (
                <option key={v} value={v}>
                  {String(v)}
                </option>
              ))}
            </select>
          </div>
          <div className="cascade-arrow" aria-hidden="true">
            →
          </div>
          <div className="filter filter-lg">
            <label>Drug</label>
            <select value={compound} onChange={(e) => setCompound(e.target.value)}>
              <option value="">{target ? `All ${target} drugs` : "All drugs"}</option>
              {compoundOptions.map((v) => (
                <option key={v} value={v}>
                  {String(v)}
                </option>
              ))}
            </select>
            {target && compoundOptions.length === 0 && (
              <span className="filter-hint">No drugs recorded for {target} yet.</span>
            )}
          </div>
          <div className="filter filter-lg">
            <label>Target family</label>
            <select value={targetFamily} onChange={(e) => setTargetFamily(e.target.value)}>
              <option value="">All families</option>
              {optionsFor("target_family").map((v) => (
                <option key={v} value={v}>
                  {String(v)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="filter-block">
          <div className="group-title">Cancer type</div>
          <div className="cancer-filters">
            <div className="filter">
              <label>Broad category</label>
              <select
                value={indicationCategory}
                onChange={(e) => onCategoryChange(e.target.value)}
              >
                <option value="">All categories</option>
                {optionsFor("indication_category").map((v) => (
                  <option key={v} value={v}>
                    {String(v)}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter">
              <label>Specific indication</label>
              <select value={indication} onChange={(e) => setIndication(e.target.value)}>
                <option value="">All indications</option>
                {indicationOptions.map((v) => (
                  <option key={v} value={v}>
                    {String(v)}
                  </option>
                ))}
              </select>
              {narrowedIndications.length > 0 && (
                <span className="filter-hint">
                  Narrowed to indications seen in {indicationCategory}.
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="filter-block">
          <div className="group-title">Therapy mode</div>
          <div className="therapy-row">
            <div className="segmented" role="group" aria-label="Therapy mode">
              {THERAPY_MODES.map(([mode, label]) => (
                <button
                  key={mode}
                  className={`seg-btn ${therapyMode === mode ? "active" : ""}`}
                  onClick={() => onTherapyModeChange(mode)}
                >
                  {label}
                </button>
              ))}
            </div>
            {therapyMode === "combo" && (
              <>
                <div className="filter">
                  <label>Regimen track</label>
                  <select
                    value={combinationTrack}
                    onChange={(e) => onTrackChange(e.target.value)}
                  >
                    <option value="">All tracks</option>
                    {optionsFor("combination_track")
                      .filter((v) => v !== "monotherapy")
                      .map((v) => (
                        <option key={v} value={v}>
                          {String(v)}
                        </option>
                      ))}
                  </select>
                </div>
                <div className="filter">
                  <label>Combination partner</label>
                  <select value={comboPartner} onChange={(e) => setComboPartner(e.target.value)}>
                    <option value="">All partners</option>
                    {comboPartnerOptions.map((v) => (
                      <option key={v} value={v}>
                        {String(v)}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </div>
          {therapyMode === "combo" && (
            <p className="filter-hint block">
              Each regimen track — chemotherapy, radiotherapy and targeted agents — can be analysed
              on its own.
            </p>
          )}
        </div>

        <div className="search-row">
          <input
            className="search-input"
            placeholder="Search e.g. CCNE1, adavosertib, ovarian, ATR, NCT number..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button className="btn" onClick={() => setShowAdd(true)}>
            + Add evidence
          </button>
          <button className="btn secondary" onClick={() => setShowMore((s) => !s)}>
            {showMore ? "Hide filters" : "More filters"}
            {secondaryActive > 0 ? ` (${secondaryActive})` : ""}
          </button>
        </div>

        {showMore && (
          <div className="filter-groups">
            {FILTER_GROUPS.map(([group, fields]) => (
              <div className="filter-block" key={group}>
                <div className="group-title">{group}</div>
                <div className="filters">
                  {fields.map(([field, label]) => (
                    <div className="filter" key={field}>
                      <label>{label}</label>
                      <select
                        value={filters[field] || ""}
                        onChange={(e) => setFilter(field, e.target.value)}
                      >
                        <option value="">Any</option>
                        {optionsFor(field).map((v) => (
                          <option key={v} value={v}>
                            {String(v)}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                  {group === "Outcome" && (
                    <>
                      <div className="filter">
                        <label>Max p-value</label>
                        <input
                          type="number"
                          step="0.001"
                          min="0"
                          max="1"
                          placeholder="e.g. 0.05"
                          value={maxP}
                          onChange={(e) => setMaxP(e.target.value)}
                        />
                      </div>
                      <div className="filter">
                        <label>From year</label>
                        <input
                          type="number"
                          step="1"
                          placeholder="e.g. 2015"
                          value={minYear}
                          onChange={(e) => setMinYear(e.target.value)}
                        />
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="active-filters">
          <span className="active-filters-label">Active filters</span>
          {activeChips.length === 0 ? (
            <span className="filter-hint">None — showing the full matrix.</span>
          ) : (
            <>
              {activeChips.map((c) => (
                <span className="chip" key={c.key}>
                  <span className="chip-key">{c.label}</span>
                  <span className="chip-value">{c.value}</span>
                  <button
                    className="chip-x"
                    onClick={c.onRemove}
                    aria-label={`Remove ${c.label} filter`}
                  >
                    ×
                  </button>
                </span>
              ))}
              <button className="btn secondary small" onClick={clearAll}>
                Clear all
              </button>
            </>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="result-meta">
          <span>
            {loading ? (
              "Loading…"
            ) : (
              <>
                <strong>{count(data.total)}</strong> matching observations
              </>
            )}
          </span>
          <span>
            Sorted by <strong>{sortBy}</strong> ({sortDir})
          </span>
        </div>

        {error && <div className="notice error">Could not load evidence: {error}</div>}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map(([col, label]) => (
                  <th key={col} onClick={() => toggleSort(col)}>
                    {label}
                    {sortBy === col ? (sortDir === "desc" ? " ▾" : " ▴") : ""}
                  </th>
                ))}
                <th className="static-col">Source</th>
                <th className="static-col"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Cell value={r.target} />
                  </td>
                  <td>
                    <Cell value={r.compound} />
                    {r.is_monotherapy === false && (
                      <>
                        {" "}
                        <span className="tag muted">
                          {r.combo_partner ? `+ ${r.combo_partner}` : "combination"}
                          {r.combination_track ? ` · ${r.combination_track}` : ""}
                        </span>
                      </>
                    )}
                  </td>
                  <td>
                    <Cell value={r.biomarker_name} />
                  </td>
                  <td>
                    <Cell value={r.indication} />
                  </td>
                  <td>
                    <Cell value={r.model_type} />
                  </td>
                  <td>
                    <Cell value={r.perturbation_type} />
                  </td>
                  <td>
                    <Tag kind="direction" value={r.direction} />
                  </td>
                  <td>
                    <Cell value={r.response_metric} />
                  </td>
                  <td>
                    <ValueCell row={r} />
                  </td>
                  <td>{num(r.effect_size)}</td>
                  <td>{num(r.p_value)}</td>
                  <td>
                    <Cell value={r.evidence_tier} />
                  </td>
                  <td>{txt(r.n)}</td>
                  <td>
                    <SourceCell row={r} />
                  </td>
                  <td>
                    <button
                      className="btn danger"
                      onClick={async () => {
                        const confirmed = window.confirm(
                          `Are you sure you want to delete this observation? ${r.compound} — ${r.biomarker_name} — ${r.indication} (${r.model_type})`
                        );
                        if (!confirmed) return;
                        await api.deleteEvidence(r.id);
                        setData((d) => ({
                          ...d,
                          items: asArray(d.items).filter((x) => x.id !== r.id),
                          total: Math.max(0, (Number(d.total) || 0) - 1),
                        }));
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={COLUMNS.length + 2} className="loading">
                    No evidence rows match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <button className="page-btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            <span className="arrow">‹</span> Prev
          </button>
          <span>
            Page {page + 1} / {totalPages}
          </span>
          <button
            className="page-btn next"
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next <span className="arrow">›</span>
          </button>
        </div>
      </div>

      {showAdd && (
        <AddEvidenceForm
          vocab={vocab}
          onClose={() => setShowAdd(false)}
          onCreated={() => {
            setShowAdd(false);
            setPage(0);
            setSortBy("id");
            setSortDir("desc");
          }}
        />
      )}
    </>
  );
}
