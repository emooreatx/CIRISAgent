async function fetchMessages() {
  const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/messages?limit=10');
  return res.json();
}

export default async function CommsPage() {
  const msgs = await fetchMessages();
  return (
    <div>
      <h1>Comms</h1>
      <pre>{JSON.stringify(msgs)}</pre>
    </div>
  );
}
