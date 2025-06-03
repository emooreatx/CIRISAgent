async function fetchTools() {
  const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/tools');
  return res.json();
}

export default async function ToolsPage() {
  const data = await fetchTools();
  return (
    <div>
      <h1>Tools</h1>
      <pre>{JSON.stringify(data)}</pre>
    </div>
  );
}
