"use client";

import React, { useState, useEffect } from "react";
import { CIRISClient } from "../../lib/cirisClient";

const client = new CIRISClient();

// Fetch deferrals from the API (audit endpoint)
async function fetchDeferrals() {
  return await client.auditList('defer');
}

async function fetchGuidance(context: any = {}) {
  return await client.toolExecute('guidance', context);
}

export default function WAPage() {
  const [deferrals, setDeferrals] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [feedback, setFeedback] = useState('');
  const [feedbackThoughtId, setFeedbackThoughtId] = useState('');
  const [guidanceResult, setGuidanceResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchDeferrals().then(setDeferrals).finally(() => setLoading(false));
  }, []);

  function handleSelect(deferral: any) {
    setSelected(deferral);
    setFeedbackThoughtId(deferral?.originator_id || deferral?.thought_id || '');
    setGuidanceResult(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    const context: any = { feedback };
    if (feedbackThoughtId) context.thought_id = feedbackThoughtId;
    if (selected) context.deferral = selected;
    const result = await fetchGuidance(context);
    setGuidanceResult(result);
    setSubmitting(false);
  }

  return (
    <div>
      <h1>Wise Authority Deferrals & Feedback</h1>
      <div style={{ display: 'flex', gap: '2rem' }}>
        <div style={{ flex: 1, minWidth: 300 }}>
          <h2>Deferral List</h2>
          {loading ? <p>Loading...</p> : deferrals.length === 0 ? <p><em>No deferrals found.</em></p> : (
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {deferrals.map((d, i) => (
                <li key={d.event_id || i} style={{ marginBottom: 8 }}>
                  <button
                    style={{ width: '100%', textAlign: 'left', background: selected === d ? '#e0e0e0' : '#fff', border: '1px solid #ccc', borderRadius: 4, padding: 8 }}
                    onClick={() => handleSelect(d)}
                  >
                    <strong>{d.event_summary || d.event_type}</strong><br />
                    <span style={{ fontSize: '0.9em', color: '#666' }}>ID: {d.thought_id || d.originator_id || d.event_id} | {d.event_timestamp}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div style={{ flex: 2, minWidth: 400 }}>
          <h2>Deferral Details</h2>
          {selected ? (
            <div style={{ marginBottom: '1rem', background: '#f8f8f8', padding: 12, borderRadius: 4 }}>
              <div><strong>Summary:</strong> {selected.event_summary}</div>
              <div><strong>Thought ID:</strong> {selected.thought_id || selected.originator_id}</div>
              <div><strong>Timestamp:</strong> {selected.event_timestamp}</div>
              <div><strong>Payload:</strong></div>
              <pre style={{ background: '#fff', padding: 8, borderRadius: 4 }}>{JSON.stringify(selected.event_payload, null, 2)}</pre>
            </div>
          ) : <p><em>Select a deferral to view details.</em></p>}
        </div>
      </div>
      <hr style={{ margin: '2rem 0' }} />
      <h2>Submit Feedback or Guidance</h2>
      <form onSubmit={handleSubmit} style={{ marginBottom: '1rem' }}>
        <div style={{ marginBottom: 8 }}>
          <label>Thought ID (optional): </label>
          <input
            type="text"
            value={feedbackThoughtId}
            onChange={e => setFeedbackThoughtId(e.target.value)}
            placeholder="Reference a thought ID or leave blank for unsolicited"
            style={{ width: 300, marginLeft: 8 }}
            disabled={submitting}
          />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>Feedback / Guidance Request:</label><br />
          <textarea
            rows={3}
            style={{ width: '100%' }}
            value={feedback}
            onChange={e => setFeedback(feedback => e.target.value)}
            placeholder="Type your feedback or guidance request here..."
            disabled={submitting}
          />
        </div>
        <button type="submit" disabled={submitting || !feedback.trim()}>Submit</button>
      </form>
      {guidanceResult && (
        <div style={{ background: '#f8f8f8', padding: 12, borderRadius: 4 }}>
          <strong>Response:</strong>
          <pre>{JSON.stringify(guidanceResult, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
