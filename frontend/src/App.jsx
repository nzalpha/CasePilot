import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import IngestTab from "./components/IngestTab.jsx";
import StatusTab from "./components/StatusTab.jsx";
import "./styles.css";

function App() {
  const [activeTab, setActiveTab] = useState("ingest");

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Knowledge ingestion</p>
          <h1>CasePilot</h1>
        </div>
        <nav className="tabs" aria-label="Primary">
          <button
            type="button"
            className={activeTab === "ingest" ? "tab active" : "tab"}
            onClick={() => setActiveTab("ingest")}
          >
            Ingest
          </button>
          <button
            type="button"
            className={activeTab === "status" ? "tab active" : "tab"}
            onClick={() => setActiveTab("status")}
          >
            Status
          </button>
        </nav>
      </header>

      {activeTab === "ingest" ? <IngestTab /> : <StatusTab />}
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
