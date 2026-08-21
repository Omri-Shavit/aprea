import React, { useEffect, useState } from "react";
import { api } from "./api";
import { authRequired, currentUser, signOut } from "./auth";
import Compounds from "./components/Compounds.jsx";
import Explorer from "./components/Explorer.jsx";
import Insights from "./components/Insights.jsx";
import Login from "./components/Login.jsx";

const TABS = [
  ["explorer", "Evidence Explorer"],
  ["compounds", "Drug Dictionary"],
  ["insights", "Insights & Ranking"],
];

export default function App() {
  const [tab, setTab] = useState("explorer");
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
            <h1>DDR Evidence Matrix</h1>
            <p>
              Searchable landscape of biomarkers associated with DNA damage response inhibitor
              response
              &nbsp;·&nbsp; <span className="dummy-data-badge"><em>public data · build in progress</em></span>
            </p>
          </div>
          <div className="header-right">
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
          {TABS.map(([key, label]) => (
            <button
              key={key}
              className={`tab ${tab === key ? "active" : ""}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      <div className="container">
        {tab === "explorer" && <Explorer vocab={vocab} />}
        {tab === "compounds" && <Compounds vocab={vocab} />}
        {tab === "insights" && <Insights vocab={vocab} />}
      </div>

      <footer className="app-footer">
        <p>
          <a href="https://github.com/Omri-Shavit" target="_blank" rel="noopener noreferrer">
            &copy; 2026 Omri Shavit
          </a>
        </p>
      </footer>
    </div>
  );
}
