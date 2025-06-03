"use client";

import React, { useState, useEffect } from "react";
import { CIRISClient } from "../../lib/cirisClient";

const client = new CIRISClient();

async function fetchLogs(filename: string, lines: number = 100) {
  try {
    return await client.logFetch(filename, lines);
  } catch (e: any) {
    return `Failed to fetch logs: ${e.message}`;
  }
}

const LOG_FILES = [
  "latest.log",
  "ciris_agent_20250602_141632.log",
  "ciris_agent_20250602_142040.log",
  // Add more log files as needed
];

export default function LogsPage() {
  const [selected, setSelected] = useState(LOG_FILES[0]);
  const [lines, setLines] = useState(100);
  const [logContent, setLogContent] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function loadLog() {
    setLoading(true);
    setLogContent("");
    const content = await fetchLogs(selected, lines);
    setLogContent(content);
    setLoading(false);
  }

  useEffect(() => { loadLog(); }, [selected, lines]);

  return (
    <div>
      <h1>Logs Viewer</h1>
      <div style={{ marginBottom: 16 }}>
        <label>Log file: </label>
        <select value={selected} onChange={e => setSelected(e.target.value)}>
          {LOG_FILES.map(f => <option key={f} value={f}>{f}</option>)}
        </select>
        <label style={{ marginLeft: 16 }}>Lines: </label>
        <input
          type="number"
          value={lines}
          min={10}
          max={1000}
          step={10}
          onChange={e => setLines(Number(e.target.value))}
          style={{ width: 80, marginLeft: 8 }}
        />
        <button onClick={loadLog} disabled={loading} style={{ marginLeft: 16 }}>
          Refresh
        </button>
      </div>
      <div style={{ background: '#111', color: '#eee', padding: 12, borderRadius: 4, fontFamily: 'monospace', fontSize: 14, minHeight: 300, maxHeight: 600, overflowY: 'auto' }}>
        {loading ? <p>Loading...</p> : <pre style={{ margin: 0 }}>{logContent}</pre>}
      </div>
    </div>
  );
}
