async function fetchMessages() {
  try {
    const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/messages?limit=10');
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    return data;
  } catch (error) {
    console.error('Failed to fetch messages:', error);
    return { error: String(error), messages: [] };
  }
}

export default async function CommsPage() {
  const data = await fetchMessages();
  
  if (data.error) {
    return (
      <div>
        <h1>Communications</h1>
        <div style={{ color: 'red', marginBottom: '1rem' }}>
          <strong>Error:</strong> {data.error}
        </div>
        <p>Unable to load messages from the API.</p>
      </div>
    );
  }

  const messages = data.messages || [];
  
  return (
    <div>
      <h1>Communications</h1>
      <p>Recent messages from the CIRIS agent:</p>
      
      {messages.length === 0 ? (
        <p><em>No messages available</em></p>
      ) : (
        <div>
          <h2>Recent Messages ({messages.length})</h2>
          <div style={{ maxHeight: '600px', overflowY: 'auto', border: '1px solid #ccc', padding: '1rem' }}>
            {messages.map((msg: any, index: number) => (
              <div key={msg.id || index} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #eee' }}>
                <div style={{ fontSize: '0.9em', color: '#666', marginBottom: '0.5rem' }}>
                  <strong>ID:</strong> {msg.id} | <strong>Author:</strong> {msg.author_id} | <strong>Time:</strong> {msg.timestamp}
                </div>
                <div>{msg.content}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
