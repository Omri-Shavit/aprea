import React, { useEffect, useRef, useState } from "react";
import {
  ALLOWED_DOMAIN,
  GOOGLE_CLIENT_ID,
  currentUser,
  decodeJwt,
  emailAllowed,
  setToken,
} from "../auth";

// Landing page: "Sign in with Google", restricted to @aprea.com accounts.
export default function Login({ onSignedIn }) {
  const btnRef = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    function handleCredential(response) {
      const token = response.credential;
      const claims = decodeJwt(token);
      if (!claims || !emailAllowed(claims)) {
        setError(`This app is restricted to @${ALLOWED_DOMAIN} accounts.`);
        return;
      }
      setToken(token);
      const user = currentUser();
      if (user) onSignedIn(user);
      else setError("Could not validate your sign-in. Please try again.");
    }

    // The GSI script loads async; poll briefly until window.google is ready.
    function tryInit() {
      if (cancelled) return;
      if (!window.google?.accounts?.id) {
        setTimeout(tryInit, 100);
        return;
      }
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredential,
        auto_select: false,
      });
      if (btnRef.current) {
        window.google.accounts.id.renderButton(btnRef.current, {
          theme: "filled_blue",
          size: "large",
          text: "signin_with",
          shape: "pill",
        });
      }
    }
    tryInit();
    return () => {
      cancelled = true;
    };
  }, [onSignedIn]);

  return (
    <div className="login-screen">
      <div className="login-card">
        <div className="login-badge">WEE1</div>
        <h1>WEE1 Inhibition • Evidence Matrix</h1>
        <p className="login-sub">
          Internal Aprea Therapeutics tool. Sign in with your{" "}
          <strong>@{ALLOWED_DOMAIN}</strong> Google account to continue.
        </p>
        <div className="login-btn" ref={btnRef}></div>
        {error && <p className="login-error">{error}</p>}
        <p className="login-foot">Access is limited to authorized Aprea personnel.</p>
      </div>
    </div>
  );
}
