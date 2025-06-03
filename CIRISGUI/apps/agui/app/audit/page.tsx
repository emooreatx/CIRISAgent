async function fetchAudit() {
  const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/audit');
  return res.json();
}

export default async function AuditPage() {
  const data = await fetchAudit();
  return (
    <div>
      <h1>Audit & Metrics</h1>
      <pre>{JSON.stringify(data)}</pre>
    </div>
  );
}
