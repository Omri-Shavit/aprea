import React, { useEffect, useState } from "react";
import { api } from "./api";
import { authRequired, currentUser, signOut } from "./auth";
import Explorer from "./components/Explorer.jsx";
import Insights from "./components/Insights.jsx";
import Login from "./components/Login.jsx";

export default function App() {
  const [tab, setTab] = useState("explorer");
  const [includeConfidential, setIncludeConfidential] = useState(true);
  const [vocab, setVocab] = useState(null);
  const [user, setUser] = useState(() => currentUser());

  const authed = !authRequired || Boolean(user);

  useEffect(() => {
    if (authed) api.vocab().then(setVocab).catch(console.error);
  }, [authed]);

  if (!authed) {
    return <Login onSignedIn={setUser} />;
  }

  return (
    <div>
      <header className="app-header">
        <div className="header-row">
          <div>
            <h1>WEE1 Inhibition • Evidence Matrix</h1>
            <p>
              Searchable landscape of biomarkers associated with WEE1-inhibitor response
              &nbsp;·&nbsp; <em>mockup with dummy data</em>
            </p>
          </div>
          <div className="header-right">
            <label className="toggle" style={{ color: "white" }}>
              <span className="switch switch--light">
                <input
                  type="checkbox"
                  checked={includeConfidential}
                  onChange={(e) => setIncludeConfidential(e.target.checked)}
                />
                <span className="slider"></span>
              </span>
              Include Aprea confidential rows
            </label>
            {user && (
              <div className="user-chip">
                <span className="user-email">{user.email}</span>
                <button
                  className="signout-btn"
                  onClick={() => {
                    signOut();
                    setUser(null);
                  }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="tabs">
          <button className={`tab ${tab === "explorer" ? "active" : ""}`} onClick={() => setTab("explorer")}>
            Evidence Explorer
          </button>
          <button className={`tab ${tab === "insights" ? "active" : ""}`} onClick={() => setTab("insights")}>
            Insights &amp; Ranking
          </button>
        </div>
      </header>

      <div className="container">
        {tab === "explorer" ? (
          <Explorer vocab={vocab} includeConfidential={includeConfidential} />
        ) : (
          <Insights includeConfidential={includeConfidential} />
        )}
      </div>
    </div>
  );
}
