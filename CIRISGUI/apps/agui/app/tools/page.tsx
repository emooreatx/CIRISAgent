"use client";

import React, { useState, useEffect } from "react";
import { CIRISClient } from "../../lib/cirisClient";

const client = new CIRISClient();

async function fetchTools() {
  return { tools: await client.toolsList() };
}

async function callTool(tool: string, args: any) {
  return await client.toolExecute(tool, args);
}

export default function ToolsPage() {
  const [tools, setTools] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [args, setArgs] = useState<string>('{}');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchTools().then(data => setTools(data.tools || [])).finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const parsed = args.trim() ? JSON.parse(args) : {};
      const res = await callTool(selected!, parsed);
      setResult(res);
    } catch (err) {
      setResult({ error: 'Invalid JSON arguments or request failed.' });
    }
    setSubmitting(false);
  }

  return (
    <div>
      <h1>Tools</h1>
      {loading ? <p>Loading...</p> : (
        <>
          <ul style={{ listStyle: 'none', padding: 0, marginBottom: 16 }}>
            {tools.map(tool => (
              <li key={tool} style={{ marginBottom: 4 }}>
                <button
                  style={{ fontWeight: selected === tool ? 'bold' : 'normal', border: '1px solid #ccc', borderRadius: 4, padding: '4px 12px', background: selected === tool ? '#e0e0e0' : '#fff' }}
                  onClick={() => { setSelected(tool); setResult(null); }}
                >
                  {tool}
                </button>
              </li>
            ))}
          </ul>
          {selected && (
            <form onSubmit={handleSubmit} style={{ marginBottom: 16 }}>
              <h2>Call Tool: {selected}</h2>
              <label>Arguments (JSON):</label><br />
              <textarea
                rows={3}
                style={{ width: '100%', marginBottom: 8 }}
                value={args}
                onChange={e => setArgs(e.target.value)}
                placeholder="{}"
                disabled={submitting}
              />
              <br />
              <button type="submit" disabled={submitting}>Call Tool</button>
            </form>
          )}
          {result && (
            <div style={{ background: '#f8f8f8', padding: 12, borderRadius: 4 }}>
              <strong>Result:</strong>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
