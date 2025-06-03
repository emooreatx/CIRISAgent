import React, { useState, useEffect } from "react";

async function fetchAuditEntries() {
  try {
    const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/audit');
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    return data.entries || [];
  } catch (error) {
    console.error('Failed to fetch audit log:', error);
    return [];
  }
}

export default function AuditPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAuditEntries().then(setEntries).catch(e => setError(String(e))).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1>Audit Log</h1>
      {loading && <p>Loading...</p>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {entries.length === 0 && !loading ? (
        <p><em>No audit entries found.</em></p>
      ) : (
        <div style={{ maxHeight: '600px', overflowY: 'auto', border: '1px solid #ccc', padding: '1rem' }}>
          {entries.map((entry, idx) => (
            <div key={entry.event_id || idx} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #eee' }}>
              <div style={{ fontSize: '0.9em', color: '#666', marginBottom: '0.5rem' }}>
                <strong>Event:</strong> {entry.event_type} | <strong>ID:</strong> {entry.event_id} | <strong>Time:</strong> {entry.event_timestamp}
              </div>
              <div><strong>Summary:</strong> {entry.event_summary}</div>
              <pre style={{ background: '#f8f8f8', padding: '0.5em', borderRadius: '4px' }}>{JSON.stringify(entry.event_payload, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
