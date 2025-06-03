async function fetchQueue() {
  const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/wa/queue');
  return res.json();
}

export default async function WAPage() {
  const queue = await fetchQueue();
  return (
    <div>
      <h1>Wise Authority</h1>
      <pre>{JSON.stringify(queue)}</pre>
    </div>
  );
}
