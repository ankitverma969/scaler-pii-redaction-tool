import { useEffect, useState } from "react";

import "./App.css";
import { checkHealth } from "./services/api";

const STATUS_LABELS = {
  connecting: "Connecting...",
  online: "API Online",
  offline: "API Unavailable",
};

function App() {
  const [apiStatus, setApiStatus] = useState("connecting");

  useEffect(() => {
    let isMounted = true;

    async function loadHealth() {
      try {
        const health = await checkHealth();
        if (isMounted) {
          setApiStatus(health.status === "ok" ? "online" : "offline");
        }
      } catch {
        if (isMounted) {
          setApiStatus("offline");
        }
      }
    }

    loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="app-card" aria-labelledby="app-title">
        <p className="eyebrow">Scaler AI Labs Assignment</p>
        <h1 id="app-title">PII Redaction Tool</h1>
        <p className="description">
          Detect and replace personally identifiable information in DOCX
          documents while preserving document structure.
        </p>
        <div className="status-row" role="status" aria-live="polite">
          <span className={`status-dot ${apiStatus}`} aria-hidden="true" />
          <span>{STATUS_LABELS[apiStatus]}</span>
        </div>
      </section>
    </main>
  );
}

export default App;
