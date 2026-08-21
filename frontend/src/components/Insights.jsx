import React, { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { api } from "../api";
import { EMPTY, asArray, count, finiteNum, fracPct, humanize, joinList, num, toCounts, txt } from "../format";

const PIE_COLORS = ["rgb(106, 40, 115)", "#2563eb", "#059669", "#d97706", "#dc2626", "#0891b2", "rgb(158, 115, 164)"];
const TARGET_COLORS = [
  "rgb(106, 40, 115)", "#2563eb", "#059669", "#d97706", "#dc2626",
  "#0891b2", "rgb(158, 115, 164)", "#7c3aed", "#be185d", "#0f766e",
  "#a16207", "#475569",
];

const SUB_SCORES = [
  ["clinical_evidence", "Clinical evidence"],
  ["reproducibility", "Reproducibility"],
  ["chemical_genetic_concordance", "Chemical–genetic concordance"],
  ["mechanistic_link", "Mechanistic link"],
  ["prevalence", "Prevalence"],
  ["attribution", "Attribution"],
  ["assay_feasibility", "Assay feasibility"],
  ["validation_feasibility", "Validation feasibility"],
];

const SUMMARY_CARDS = [
  ["total_entries", "Observations"],
  ["n_targets", "DDR targets"],
  ["n_compounds", "Compounds"],
  ["n_biomarkers", "Biomarkers"],
  ["n_indications", "Indications"],
  ["n_trials", "Trials"],
  ["n_clinical", "Clinical rows"],
  ["n_preclinical", "Preclinical rows"],
  ["pct_predictive", "% predictive", "pct"],
  ["pct_randomized_interaction", "% randomized interaction", "pct"],
];

// green (sensitive) -> red (resistant) scale for the landscape heatmap
function heatColor(frac) {
  const f = Number.isFinite(Number(frac)) ? Math.min(1, Math.max(0, Number(frac))) : 0.5;
  const r = Math.round(220 - f * (220 - 5));
  const g = Math.round(38 + f * (150 - 38));
  return `rgb(${r},${g},60)`;
}

// rows / columns may be plain strings or {name} records.
function labelList(input) {
  return asArray(input)
    .map((x) => (x && typeof x === "object" ? String(x.name ?? x.key ?? x.label ?? "") : String(x)))
    .filter(Boolean);
}

// target-overview returns [{biomarker_name, n}] — the supporting row count is
// worth showing, since these are ranked by volume studied, not by score.
function topBiomarkers(list) {
  const parts = asArray(list)
    .map((b) => {
      if (!b) return "";
      if (typeof b !== "object") return String(b);
      const name = b.biomarker_name ?? b.name ?? b.key ?? "";
      const n = finiteNum(b.n ?? b.count);
      return name ? (n === null ? String(name) : `${name} (${count(n)})`) : "";
    })
    .filter(Boolean);
  return parts.length ? parts.join(" · ") : "";
}

// Cell keys differ between by=compound and by=target modes.
function findCell(cells, rowName, colName) {
  return asArray(cells).find((c) => {
    const r = c?.row ?? c?.indication ?? c?.indication_category ?? c?.row_name;
    const k = c?.column ?? c?.compound ?? c?.target ?? c?.col ?? c?.column_name;
    return String(r) === String(rowName) && String(k) === String(colName);
  });
}

function cellFrac(cell) {
  return finiteNum(cell?.frac_sensitive ?? cell?.frac ?? cell?.value);
}

function cellCount(cell) {
  return finiteNum(cell?.n ?? cell?.count);
}

function Empty({ children }) {
  return <div className="loading">{children}</div>;
}

export default function Insights({ vocab }) {
  const [target, setTarget] = useState("");
  const [landscapeBy, setLandscapeBy] = useState("compound");
  const [selectedBiomarker, setSelectedBiomarker] = useState("");
  const [compositionKey, setCompositionKey] = useState("");
  const [summary, setSummary] = useState(null);
  const [ranking, setRanking] = useState([]);
  const [composition, setComposition] = useState(null);
  const [landscape, setLandscape] = useState(null);
  const [volcano, setVolcano] = useState([]);
  const [overview, setOverview] = useState([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState([]);

  useEffect(() => {
    setLoading(true);
    const scope = { target: target || undefined };
    const calls = [
      ["summary", api.summary(scope), setSummary],
      ["biomarker ranking", api.biomarkerRanking(scope), (v) => setRanking(asArray(v))],
      ["composition", api.composition(scope), setComposition],
      ["volcano", api.volcano(scope), (v) => setVolcano(asArray(v))],
      ["target overview", api.targetOverview(scope), (v) => setOverview(asArray(v))],
    ];
    let cancelled = false;
    Promise.allSettled(calls.map(([, p]) => p)).then((results) => {
      if (cancelled) return;
      const bad = [];
      results.forEach((res, i) => {
        const [name, , setter] = calls[i];
        if (res.status === "fulfilled") setter(res.value);
        else {
          bad.push(name);
          console.error(name, res.reason);
        }
      });
      setFailed(bad);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [target]);

  useEffect(() => {
    let cancelled = false;
    api
      .indicationLandscape({ target: target || undefined, by: landscapeBy })
      .then((v) => {
        if (!cancelled) setLandscape(v);
      })
      .catch((e) => {
        console.error(e);
        if (!cancelled) setLandscape(null);
      });
    return () => {
      cancelled = true;
    };
  }, [target, landscapeBy]);

  const targetOptions = useMemo(() => {
    const fromVocab = asArray(vocab?.target);
    if (fromVocab.length) return fromVocab;
    return [...new Set(asArray(overview).map((r) => r?.target).filter(Boolean))].sort();
  }, [vocab, overview]);

  const compositionKeys = useMemo(
    () => (composition && typeof composition === "object" ? Object.keys(composition) : []),
    [composition]
  );
  const activeCompositionKey =
    compositionKey && compositionKeys.includes(compositionKey)
      ? compositionKey
      : compositionKeys.find((k) => k === "by_target") || compositionKeys[0] || "";
  const compositionRows = toCounts(composition?.[activeCompositionKey]);
  const sourceRows = toCounts(composition?.by_source_type);

  const rankingRows = useMemo(
    () =>
      asArray(ranking)
        .map((d) => ({ ...d, composite_score: finiteNum(d?.composite_score) ?? 0 }))
        .filter((d) => d.biomarker_name),
    [ranking]
  );
  const detail =
    rankingRows.find((d) => d.biomarker_name === selectedBiomarker) || rankingRows[0] || null;

  const volcanoPoints = useMemo(
    () =>
      asArray(volcano)
        .map((p) => ({
          ...p,
          effect_size: finiteNum(p?.effect_size),
          neg_log10_p: finiteNum(p?.neg_log10_p),
          n: finiteNum(p?.n) ?? 1,
        }))
        .filter((p) => p.effect_size !== null && p.neg_log10_p !== null),
    [volcano]
  );
  const volcanoTargets = useMemo(
    () => [...new Set(volcanoPoints.map((p) => p.target).filter(Boolean))].sort(),
    [volcanoPoints]
  );
  const targetColor = (t) => {
    const i = volcanoTargets.indexOf(t);
    return i < 0 ? "#94a3b8" : TARGET_COLORS[i % TARGET_COLORS.length];
  };

  const sensRes = [
    { name: "sensitive", value: finiteNum(summary?.n_sensitive) ?? 0 },
    { name: "resistant", value: finiteNum(summary?.n_resistant) ?? 0 },
  ];
  const hasSensRes = sensRes.some((d) => d.value > 0);

  const landscapeRows = labelList(landscape?.rows);
  const landscapeCols = labelList(landscape?.columns);

  if (loading && !summary) return <Empty>Loading insights…</Empty>;

  return (
    <>
      <div className="panel scope-panel">
        <div className="scope-row">
          <div className="filter filter-lg">
            <label>Scope all insights to a target</label>
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">All DDR targets</option>
              {targetOptions.map((t) => (
                <option key={t} value={t}>
                  {String(t)}
                </option>
              ))}
            </select>
          </div>
          <p className="sub" style={{ margin: 0 }}>
            Every panel below (summary, ranking, volcano, composition and landscape) is recomputed
            for the selected target.
          </p>
        </div>
      </div>

      {failed.length > 0 && (
        <div className="notice error">Could not load: {failed.join(", ")}.</div>
      )}

      <div className="panel">
        <h2>Target overview</h2>
        <p className="sub">
          Coverage per DDR target. Click a target to scope every panel on this tab to it.
        </p>
        {asArray(overview).length === 0 ? (
          <Empty>No targets in the database yet.</Empty>
        ) : (
          <div className="target-cards">
            {asArray(overview).map((t, i) => (
              <button
                key={t?.target || i}
                className={`target-card ${target && target === t?.target ? "active" : ""}`}
                onClick={() => setTarget(target === t?.target ? "" : t?.target || "")}
              >
                <div className="target-card-head">
                  <span className="target-name">{txt(t?.target)}</span>
                  <span className="tag muted">
                    {count(t?.n_rows)} {Number(t?.n_rows) === 1 ? "row" : "rows"}
                  </span>
                </div>
                <div className="target-stats">
                  <span>
                    <strong>{count(t?.n_compounds)}</strong> drugs
                  </span>
                  <span>
                    <strong>{count(t?.n_biomarkers)}</strong> biomarkers
                  </span>
                  <span>
                    <strong>{count(t?.n_indications)}</strong> indications
                  </span>
                  <span>
                    <strong>{count(t?.n_clinical)}</strong> clinical
                  </span>
                  <span>
                    sensitive <strong>{fracPct(t?.frac_sensitive)}</strong>
                  </span>
                </div>
                <div className="target-biomarkers">
                  {topBiomarkers(t?.top_biomarkers) || (
                    <span className="muted-cell">No biomarkers yet</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="cards">
        {SUMMARY_CARDS.map(([k, label, kind]) => (
          <div className="card" key={k}>
            <div className="value">
              {summary && summary[k] !== null && summary[k] !== undefined
                ? kind === "pct"
                  ? `${summary[k]}%`
                  : count(summary[k])
                : EMPTY}
            </div>
            <div className="label">{label}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Candidate biomarker ranking</h2>
        <p className="sub">
          Composite score aggregates eight weighted sub-scores (clinical evidence, reproducibility,
          chemical–genetic concordance, mechanistic link, prevalence, attribution, assay and
          validation feasibility). Bars are coloured by fraction of &ldquo;sensitive&rdquo;
          observations; select a biomarker to see the breakdown behind its rank.
        </p>
        {rankingRows.length === 0 ? (
          <Empty>No biomarkers scored yet.</Empty>
        ) : (
          <div className="rank-layout">
            <div className="rank-chart">
              <ResponsiveContainer width="100%" height={Math.max(260, rankingRows.length * 30)}>
                <BarChart layout="vertical" data={rankingRows} margin={{ left: 60, right: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" dataKey="composite_score" fontSize={11} />
                  <YAxis type="category" dataKey="biomarker_name" width={170} fontSize={11} />
                  <Tooltip content={<RankTooltip />} />
                  <Bar
                    dataKey="composite_score"
                    radius={[0, 4, 4, 0]}
                    onClick={(d) => setSelectedBiomarker(d?.biomarker_name || "")}
                    cursor="pointer"
                  >
                    {rankingRows.map((d, i) => (
                      <Cell key={i} fill={heatColor(d.frac_sensitive)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="legend">
                <span>
                  <span className="dot" style={{ background: heatColor(1) }} />
                  mostly sensitive
                </span>
                <span>
                  <span className="dot" style={{ background: heatColor(0.5) }} />
                  mixed
                </span>
                <span>
                  <span className="dot" style={{ background: heatColor(0) }} />
                  mostly resistant
                </span>
              </div>
            </div>

            <div className="rank-detail">
              <div className="filter">
                <label>Biomarker detail</label>
                <select
                  value={detail?.biomarker_name || ""}
                  onChange={(e) => setSelectedBiomarker(e.target.value)}
                >
                  {rankingRows.map((d) => (
                    <option key={d.biomarker_name} value={d.biomarker_name}>
                      {d.biomarker_name}
                    </option>
                  ))}
                </select>
              </div>
              {detail && (
                <>
                  <div className="detail-meta">
                    <strong>{detail.biomarker_name}</strong>
                    <span className="tag muted">{txt(detail.biomarker_type)}</span>
                    {detail.biomarker_scope && (
                      <span className="tag muted">{detail.biomarker_scope}</span>
                    )}
                  </div>
                  <div className="detail-grid">
                    <span>Composite</span>
                    <span>{num(detail.composite_score)}</span>
                    <span>Studies / datasets</span>
                    <span>
                      {txt(detail.n_studies)} / {txt(detail.n_datasets)}
                    </span>
                    <span>Targets</span>
                    <span>{joinList(detail.targets)}</span>
                    <span>Sensitive</span>
                    <span>{fracPct(detail.frac_sensitive)}</span>
                    <span>Mean |effect|</span>
                    <span>{num(detail.mean_abs_effect)}</span>
                    <span>% clinical / predictive</span>
                    <span>
                      {txt(detail.pct_clinical)} / {txt(detail.pct_predictive)}
                    </span>
                  </div>
                  <div className="group-title">Sub-scores</div>
                  <SubScores row={detail} />
                </>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Effect size vs significance (volcano)</h2>
          <p className="sub">
            Points are coloured by target. Only the quantitatively tested subset appears here:{" "}
            <strong>{volcanoPoints.length}</strong> of {asArray(volcano).length} rows carry both an
            effect size and a p-value. Registry and literature rows usually report neither, so their
            absence is expected rather than missing data.
          </p>
          {volcanoPoints.length === 0 ? (
            <Empty>No rows with both an effect size and a p-value yet.</Empty>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={340}>
                <ScatterChart margin={{ left: 10, right: 20, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="effect_size"
                    name="effect size"
                    fontSize={11}
                    label={{ value: "effect size", position: "insideBottom", offset: -5, fontSize: 11 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="neg_log10_p"
                    name="-log10(p)"
                    fontSize={11}
                    label={{ value: "-log10(p)", angle: -90, position: "insideLeft", fontSize: 11 }}
                  />
                  <ZAxis type="number" dataKey="n" range={[20, 220]} name="n" />
                  <Tooltip content={<VolcanoTooltip />} cursor={{ strokeDasharray: "3 3" }} />
                  {(volcanoTargets.length ? volcanoTargets : [null]).map((t) => (
                    <Scatter
                      key={t || "untargeted"}
                      data={volcanoPoints.filter((p) => (t ? p.target === t : !p.target))}
                      fill={targetColor(t)}
                      fillOpacity={0.65}
                    />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
              <div className="legend">
                {volcanoTargets.map((t) => (
                  <span key={t}>
                    <span className="dot" style={{ background: targetColor(t) }} />
                    {t}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="panel">
          <h2>Evidence composition</h2>
          <p className="sub">
            Where the evidence comes from, and the sensitive / resistant split of directional rows.
          </p>
          {sourceRows.length === 0 && !hasSensRes ? (
            <Empty>No evidence to summarise yet.</Empty>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                {sourceRows.length > 0 && (
                  <Pie
                    data={sourceRows}
                    dataKey="count"
                    nameKey="name"
                    cx="30%"
                    cy="50%"
                    outerRadius={78}
                    label={(e) => e.name}
                  >
                    {sourceRows.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                )}
                {hasSensRes && (
                  <Pie
                    data={sensRes}
                    dataKey="value"
                    nameKey="name"
                    cx="75%"
                    cy="50%"
                    innerRadius={44}
                    outerRadius={78}
                    label={(e) => e.name}
                  >
                    <Cell fill="#059669" />
                    <Cell fill="#dc2626" />
                  </Pie>
                )}
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}

          {compositionKeys.length > 0 && (
            <>
              <div className="filter" style={{ maxWidth: 260, marginTop: 6 }}>
                <label>Breakdown</label>
                <select
                  value={activeCompositionKey}
                  onChange={(e) => setCompositionKey(e.target.value)}
                >
                  {compositionKeys.map((k) => (
                    <option key={k} value={k}>
                      {humanize(k.replace(/^by_/, ""))}
                    </option>
                  ))}
                </select>
              </div>
              {compositionRows.length === 0 ? (
                <Empty>No values recorded for this breakdown.</Empty>
              ) : (
                <ResponsiveContainer width="100%" height={Math.max(180, compositionRows.length * 26)}>
                  <BarChart layout="vertical" data={compositionRows} margin={{ left: 40, right: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" dataKey="count" fontSize={11} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={150} fontSize={11} />
                    <Tooltip />
                    <Bar dataKey="count" fill="var(--accent)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>Indication landscape</h2>
            <p className="sub">
              Cell = fraction of &ldquo;sensitive&rdquo; observations (green→red), number =
              supporting rows. Blank = no data for that pair.
            </p>
          </div>
          <div className="segmented" role="group" aria-label="Landscape columns">
            {[
              ["compound", "By drug"],
              ["target", "By target"],
            ].map(([mode, label]) => (
              <button
                key={mode}
                className={`seg-btn ${(landscape?.mode || landscapeBy) === mode ? "active" : ""}`}
                onClick={() => setLandscapeBy(mode)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {landscapeRows.length === 0 || landscapeCols.length === 0 ? (
          <Empty>Not enough data to build the landscape yet.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="landscape-table">
              <thead>
                <tr>
                  <th className="static-col">Indication</th>
                  {landscapeCols.map((c) => (
                    <th key={c} className="static-col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {landscapeRows.map((rowName) => (
                  <tr key={rowName}>
                    <td>
                      <strong>{rowName}</strong>
                    </td>
                    {landscapeCols.map((colName) => {
                      const cell = findCell(landscape?.cells, rowName, colName);
                      const frac = cellFrac(cell);
                      const n = cellCount(cell);
                      return (
                        <td key={colName}>
                          {cell && frac !== null ? (
                            <span
                              className="tag"
                              style={{ background: heatColor(frac), color: "white" }}
                            >
                              {Math.round(frac * 100)}%{n !== null ? ` · n=${n}` : ""}
                            </span>
                          ) : cell && n !== null ? (
                            <span className="tag muted">n={n}</span>
                          ) : (
                            <span className="muted-cell">{EMPTY}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function SubScores({ row }) {
  const values = SUB_SCORES.map(([k, label]) => [label, finiteNum(row?.[k])]);
  const max = values.reduce((m, [, v]) => (v !== null && v > m ? v : m), 1);
  if (values.every(([, v]) => v === null)) {
    return <Empty>No sub-scores reported for this biomarker.</Empty>;
  }
  return (
    <div className="subscores">
      {values.map(([label, v]) => (
        <div className="subscore" key={label}>
          <span className="subscore-label">{label}</span>
          <span className="subscore-track">
            <span
              className="subscore-fill"
              style={{ width: v === null ? 0 : `${Math.min(100, (v / max) * 100)}%` }}
            />
          </span>
          <span className="subscore-value">{v === null ? EMPTY : num(v)}</span>
        </div>
      ))}
    </div>
  );
}

function RankTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="panel" style={{ margin: 0, padding: 10, fontSize: 12 }}>
      <strong>{txt(d.biomarker_name)}</strong> ({txt(d.biomarker_type)})<br />
      score: {num(d.composite_score)}<br />
      studies: {txt(d.n_studies)} · sensitive: {fracPct(d.frac_sensitive)}<br />
      mean|effect|: {num(d.mean_abs_effect)}<br />
      % predictive: {txt(d.pct_predictive)} · % clinical: {txt(d.pct_clinical)}<br />
      targets: {joinList(d.targets)}
    </div>
  );
}

function VolcanoTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="panel" style={{ margin: 0, padding: 10, fontSize: 12 }}>
      <strong>{txt(d.biomarker_name)}</strong><br />
      {txt(d.target)} · {txt(d.compound)}<br />
      {txt(d.indication)}<br />
      {d.combination_track ? <>track: {d.combination_track}<br /></> : null}
      effect: {num(d.effect_size)} · -log10(p): {num(d.neg_log10_p)}<br />
      n={txt(d.n)} · {txt(d.evidence_tier)}
    </div>
  );
}
