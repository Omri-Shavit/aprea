// Thin wrapper around the FastAPI backend.
//
// Base URL:
//   * Local dev  -> VITE_API_BASE_URL unset => relative "/api" (Vite proxy).
//   * Production -> VITE_API_BASE_URL = https://<cloud-run-url> (cross-origin).
// Auth: attaches the Google ID token as a bearer header when signed in, and
// clears the session + reloads (back to login) on a 401.

import { clearToken, getToken } from "./auth";

const BASE = import.meta.env.VITE_API_BASE_URL || "";
const API = `${BASE}/api`;

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function handle(res, path) {
  if (res.status === 401) {
    clearToken();
    window.location.reload(); // bounce back to the login screen
    throw new Error("Session expired");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} on ${path}`);
  if (res.status === 204) return true;
  return res.json();
}

async function get(path, params = {}) {
  const url = new URL(API + path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  const res = await fetch(url, { headers: authHeaders() });
  return handle(res, path);
}

export const api = {
  listEvidence: (params) => get("/evidence", params),
  vocab: () => get("/vocab"),
  summary: (includeConfidential) =>
    get("/insights/summary", { include_confidential: includeConfidential }),
  composition: (includeConfidential) =>
    get("/insights/composition", { include_confidential: includeConfidential }),
  biomarkerRanking: (includeConfidential) =>
    get("/insights/biomarker-ranking", { include_confidential: includeConfidential }),
  indicationLandscape: (includeConfidential) =>
    get("/insights/indication-landscape", { include_confidential: includeConfidential }),
  volcano: (includeConfidential) =>
    get("/insights/volcano", { include_confidential: includeConfidential }),

  createEvidence: async (body) => {
    const res = await fetch(API + "/evidence", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    return handle(res, "/evidence");
  },
  deleteEvidence: async (id) => {
    const res = await fetch(`${API}/evidence/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    return handle(res, `/evidence/${id}`);
  },
};
