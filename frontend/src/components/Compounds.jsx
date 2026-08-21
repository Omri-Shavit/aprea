import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { EMPTY, asArray, joinList, txt } from "../format";

const COLUMNS = [
  "Compound",
  "Aliases",
  "Target",
  "Developer",
  "Clinical stage",
  "Selectivity",
  "Known off-target activity",
  "Typical dose",
  "Typical schedule",
  "ChEMBL",
];

function Cell({ value }) {
  if (value === null || value === undefined || value === "") {
    return <span className="muted-cell">{EMPTY}</span>;
  }
  return <>{String(value)}</>;
}

function ChemblCell({ id }) {
  if (!id) return <span className="muted-cell">{EMPTY}</span>;
  return (
    <a
      className="source-link"
      href={`https://www.ebi.ac.uk/chembl/compound_report_card/${id}/`}
      target="_blank"
      rel="noopener noreferrer"
    >
      {id}
    </a>
  );
}

export default function Compounds({ vocab }) {
  const [q, setQ] = useState("");
  const [target, setTarget] = useState("");
  const [targetFamily, setTargetFamily] = useState("");
  const [includeTools, setIncludeTools] = useState(true);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => {
      api
        .compounds({
          q,
          target: target || undefined,
          target_family: targetFamily || undefined,
          include_tool_compounds: includeTools,
        })
        .then((res) => {
          setRows(Array.isArray(res) ? res : asArray(res?.items));
          setError(null);
        })
        .catch((e) => {
          console.error(e);
          setError(String(e?.message || e));
          setRows([]);
        })
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q, target, targetFamily, includeTools]);

  // One block per target so the dictionary reads as a per-target agent list.
  const groups = useMemo(() => {
    const byTarget = new Map();
    asArray(rows).forEach((r) => {
      const key = r?.target || "Unassigned target";
      if (!byTarget.has(key)) byTarget.set(key, []);
      byTarget.get(key).push(r);
    });
    return [...byTarget.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([name, list]) => [
        name,
        [...list].sort((a, b) =>
          String(a?.canonical_name || "").localeCompare(String(b?.canonical_name || ""))
        ),
      ]);
  }, [rows]);

  const targetOptions = useMemo(() => {
    const fromVocab = asArray(vocab?.target);
    if (fromVocab.length) return fromVocab;
    return [...new Set(asArray(rows).map((r) => r?.target).filter(Boolean))].sort();
  }, [vocab, rows]);

  return (
    <div className="panel">
      <h2>Drug dictionary</h2>
      <p className="sub">
        Controlled list of DDR-directed agents and tool compounds, annotated for selectivity, dose,
        schedule and known off-target activity. Grouped by primary target.
      </p>

      <div className="search-row">
        <input
          className="search-input"
          placeholder="Search name, alias or developer…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="filter">
          <label>Target</label>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">All targets</option>
            {targetOptions.map((v) => (
              <option key={v} value={v}>
                {String(v)}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label>Target family</label>
          <select value={targetFamily} onChange={(e) => setTargetFamily(e.target.value)}>
            <option value="">All families</option>
            {asArray(vocab?.target_family).map((v) => (
              <option key={v} value={v}>
                {String(v)}
              </option>
            ))}
          </select>
        </div>
        <label className="toggle">
          <span className="switch">
            <input
              type="checkbox"
              checked={includeTools}
              onChange={(e) => setIncludeTools(e.target.checked)}
            />
            <span className="slider"></span>
          </span>
          Include tool compounds
        </label>
      </div>

      <div className="result-meta">
        <span>
          {loading ? (
            "Loading…"
          ) : (
            <>
              <strong>{asArray(rows).length}</strong> agents across {groups.length}{" "}
              {groups.length === 1 ? "target" : "targets"}
            </>
          )}
        </span>
      </div>

      {error && <div className="notice error">Could not load the drug dictionary: {error}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th key={c} className="static-col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map(([groupName, list]) => (
              <React.Fragment key={groupName}>
                <tr className="group-row">
                  <td colSpan={COLUMNS.length}>
                    {groupName}
                    <span className="group-count">
                      {list.length} {list.length === 1 ? "agent" : "agents"}
                    </span>
                  </td>
                </tr>
                {list.map((r, i) => (
                  <tr key={r?.id ?? `${groupName}-${i}`}>
                    <td>
                      <strong>{txt(r?.canonical_name)}</strong>
                      {r?.is_tool_compound && (
                        <>
                          {" "}
                          <span className="tag tool">tool compound</span>
                        </>
                      )}
                      {r?.notes && (
                        <div className="cell-note" title={r.notes}>
                          {r.notes}
                        </div>
                      )}
                    </td>
                    <td className="wrap-col">{joinList(r?.aliases)}</td>
                    <td>
                      <Cell value={r?.target} />
                      {r?.secondary_targets && (
                        <div className="cell-note">also {joinList(r.secondary_targets)}</div>
                      )}
                      {r?.target_family && <div className="cell-note">{r.target_family}</div>}
                    </td>
                    <td>
                      <Cell value={r?.developer} />
                    </td>
                    <td>
                      <Cell value={r?.clinical_stage} />
                    </td>
                    <td className="wrap-col">
                      <Cell value={r?.selectivity} />
                    </td>
                    <td className="wrap-col">
                      <Cell value={r?.off_target_activity} />
                    </td>
                    <td>
                      <Cell value={r?.typical_dose} />
                    </td>
                    <td>
                      <Cell value={r?.typical_schedule} />
                    </td>
                    <td>
                      <ChemblCell id={r?.chembl_id} />
                    </td>
                  </tr>
                ))}
              </React.Fragment>
            ))}
            {!loading && groups.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="loading">
                  No compounds match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
