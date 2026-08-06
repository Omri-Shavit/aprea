// Client-side auth helpers for Google Sign-In.
//
// IMPORTANT: this only controls what the UI shows. Real enforcement happens in
// the backend (it verifies the same ID token). If VITE_GOOGLE_CLIENT_ID is unset
// (local dev), the login gate is disabled and no token is sent.

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
export const ALLOWED_DOMAIN = import.meta.env.VITE_ALLOWED_DOMAIN || "aprea.com";
export const authRequired = Boolean(GOOGLE_CLIENT_ID);

const TOKEN_KEY = "wee1_id_token";

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

// Decode a JWT payload (no verification — that's the backend's job).
export function decodeJwt(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function emailAllowed(claims) {
  if (!claims) return false;
  const email = (claims.email || "").toLowerCase();
  return claims.hd === ALLOWED_DOMAIN || email.endsWith(`@${ALLOWED_DOMAIN}`);
}

// Returns the current signed-in user (from a non-expired stored token), or null.
export function currentUser() {
  const token = getToken();
  if (!token) return null;
  const claims = decodeJwt(token);
  if (!claims) return null;
  if (claims.exp && Date.now() / 1000 >= claims.exp) {
    clearToken();
    return null;
  }
  if (!emailAllowed(claims)) return null;
  return {
    email: claims.email,
    name: claims.name,
    picture: claims.picture,
    hd: claims.hd,
  };
}

export function signOut() {
  clearToken();
  if (window.google?.accounts?.id) {
    window.google.accounts.id.disableAutoSelect();
  }
}
