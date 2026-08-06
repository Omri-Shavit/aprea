import React, { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { api } from "../api";

const PIE_COLORS = ["rgb(106, 40, 115)", "#2563eb", "#059669", "#d97706", "#dc2626", "#0891b2", "rgb(158, 115, 164)"];

// green (sensitive) -> red (resistant) scale for the landscape heatmap
function heatColor(frac) {
  const r = Math.round(220 - frac * (220 - 5));
  const g = Math.round(38 + frac * (150 - 38));
  const b = 60;
  return `rgb(${r},${g},${b})`;
}

export default function Insights({ includeConfidential }) {
  const [summary, setSummary] = useState(null);
  const [ranking, setRanking] = useState([]);
  const [composition, setComposition] = useState(null);
  const [landscape, setLandscape] = useState(null);
  const [volcano, setVolcano] = useState([]);

  useEffect(() => {
    const ic = includeConfidential;
    Promise.all([
      api.summary(ic), api.biomarkerRanking(ic), api.composition(ic),
      api.indicationLandscape(ic), api.volcano(ic),
    ]).then(([s, r, c, l, v]) => {
      setSummary(s); setRanking(r); setComposition(c); setLandscape(l); setVolcano(v);
    }).catch(console.error);
  }, [includeConfidential]);

  if (!summary) return <div className="loading">Loading insights…</div>;

  const cards = [
    ["total_entries", "Observations"],
    ["n_biomarkers", "Biomarkers"],
    ["n_compounds", "Compounds"],
    ["n_indications", "Indications"],
    ["n_clinical", "Clinical rows"],
    ["pct_predictive", "% predictive"],
    ["n_confidential", "Aprea rows"],
  ];

  const sensRes = [
    { name: "sensitive", value: summary.n_sensitive },
    { name: "resistant", value: summary.n_resistant },
  ];

  return (
    <>
      <div className="cards">
        {cards.map(([k, label]) => (
          <div className="card" key={k}>
            <div className="value">{summary[k]}{k === "pct_predictive" ? "%" : ""}</div>
            <div className="label">{label}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Candidate biomarker ranking</h2>
        <p className="sub">
          Composite score = mean|effect| × reproducibility × evidence-tier × source-quality ×
          directional-consistency × support. A transparent heuristic • tune weights in
          <code> backend/insights.py</code>. Bars colored by fraction of "sensitive" observations.
        </p>
        <ResponsiveContainer width="100%" height={Math.max(260, ranking.length * 30)}>
          <BarChart layout="vertical" data={ranking} margin={{ left: 60, right: 30 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" dataKey="composite_score" fontSize={11} />
            <YAxis type="category" dataKey="biomarker_name" width={170} fontSize={11} />
            <Tooltip content={<RankTooltip />} />
            <Bar dataKey="composite_score" radius={[0, 4, 4, 0]}>
              {ranking.map((d, i) => (
                <Cell key={i} fill={heatColor(d.frac_sensitive)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="legend">
          <span><span className="dot" style={{ background: heatColor(1) }} />mostly sensitive</span>
          <span><span className="dot" style={{ background: heatColor(0.5) }} />mixed</span>
          <span><span className="dot" style={{ background: heatColor(0) }} />mostly resistant</span>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Effect size vs significance (volcano)</h2>
          <p className="sub">Each point = one observation. Up = more significant; right = larger effect. Green sensitive, red resistant.</p>
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ left: 10, right: 20, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" dataKey="effect_size" name="effect size" fontSize={11}
                label={{ value: "effect size", position: "insideBottom", offset: -5, fontSize: 11 }} />
              <YAxis type="number" dataKey="neg_log10_p" name="-log10(p)" fontSize={11}
                label={{ value: "-log10(p)", angle: -90, position: "insideLeft", fontSize: 11 }} />
              <ZAxis type="number" dataKey="n" range={[20, 220]} name="n" />
              <Tooltip content={<VolcanoTooltip />} cursor={{ strokeDasharray: "3 3" }} />
              <Scatter data={volcano.filter((p) => p.direction === "sensitive")} fill="#059669" fillOpacity={0.6} />
              <Scatter data={volcano.filter((p) => p.direction === "resistant")} fill="#dc2626" fillOpacity={0.6} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <h2>Evidence composition</h2>
          <p className="sub">Where the evidence comes from (by source type) and sensitive/resistant split.</p>
          <ResponsiveContainer width="100%" height={340}>
            <PieChart>
              <Pie data={composition.by_source_type} dataKey="count" nameKey="key" cx="30%" cy="50%" outerRadius={80} label={(e) => e.key}>
                {composition.by_source_type.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Pie data={sensRes} dataKey="value" nameKey="name" cx="75%" cy="50%" innerRadius={45} outerRadius={80} label={(e) => e.name}>
                <Cell fill="#059669" /><Cell fill="#dc2626" />
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel">
        <h2>Indication × regimen landscape</h2>
        <p className="sub">
          Cell = fraction of "sensitive" observations (green→red), number = supporting rows. Blank = no data.
          This is the indication-by-regimen view Julie asked for.
        </p>
        <div className="table-wrap">
          <table className="landscape-table">
            <thead>
              <tr>
                <th>Indication</th>
                {landscape.compounds.map((c) => <th key={c}>{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {landscape.indications.map((ind) => (
                <tr key={ind}>
                  <td><strong>{ind}</strong></td>
                  {landscape.compounds.map((comp) => {
                    const cell = landscape.cells.find((x) => x.indication === ind && x.compound === comp);
                    return (
                      <td key={comp}>
                        {cell ? (
                          <span className="tag" style={{ background: heatColor(cell.frac_sensitive), color: "white" }}>
                            {Math.round(cell.frac_sensitive * 100)}% · n={cell.n}
                          </span>
                        ) : <span className="tag muted">•</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function RankTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="panel" style={{ margin: 0, padding: 10, fontSize: 12 }}>
      <strong>{d.biomarker_name}</strong> ({d.biomarker_type})<br />
      score: {d.composite_score}<br />
      studies: {d.n_studies} · sensitive: {Math.round(d.frac_sensitive * 100)}%<br />
      mean|effect|: {d.mean_abs_effect} · repro: {d.reproducibility_score}<br />
      % predictive: {d.pct_predictive} · % clinical: {d.pct_clinical}
    </div>
  );
}

function VolcanoTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="panel" style={{ margin: 0, padding: 10, fontSize: 12 }}>
      <strong>{d.biomarker_name}</strong><br />
      {d.compound} · {d.indication}<br />
      effect: {d.effect_size} · -log10(p): {d.neg_log10_p}<br />
      n={d.n} · {d.evidence_tier}
    </div>
  );
}
