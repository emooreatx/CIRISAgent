async function fetchScopes() {
  const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/memory/scopes');
  return res.json();
}

export default async function MemoryPage() {
  const scopes = await fetchScopes();
  return (
    <div>
      <h1>Memory</h1>
      <pre>{JSON.stringify(scopes)}</pre>
    </div>
  );
}
