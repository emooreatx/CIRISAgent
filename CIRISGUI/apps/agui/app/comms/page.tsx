"use client";

import React, { useState, useEffect } from "react";

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

async function sendMessage(content: string) {
  const res = await fetch(process.env.NEXT_PUBLIC_CIRIS_API_URL + '/v1/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      channel_id: 'gui',
      author_id: 'gui_user',
      author_name: 'GUI User',
    }),
  });
  return res.json();
}

export default function CommsPage() {
  const [messages, setMessages] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  async function loadMessages() {
    setLoading(true);
    const data = await fetchMessages();
    setLoading(false);
    if (data.error) setError(data.error);
    else {
      setError(null);
      setMessages(data.messages || []);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    setSending(true);
    await sendMessage(input);
    setInput('');
    await loadMessages();
    setSending(false);
  }

  // Auto-refresh every 5 seconds
  useEffect(() => {
    loadMessages();
    const interval = setInterval(loadMessages, 5000);
    return () => clearInterval(interval);
  }, []);

  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function handleInputKeyDown(e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  }

  function formatTime(ts: string) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleString();
  }

  return (
    <div>
      <h1>Communications</h1>
      <form onSubmit={handleSubmit} style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center' }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="Type a message to the agent..."
          style={{ width: '60%', marginRight: '1rem', minHeight: 40 }}
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()} style={{ marginRight: 8 }}>
          {sending ? 'Sending...' : 'Send'}
        </button>
        <button type="button" onClick={loadMessages} disabled={loading}>
          Refresh
        </button>
      </form>
      {error && (
        <div style={{ color: 'red', marginBottom: '1rem' }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      {loading && <p>Loading messages...</p>}
      {messages.length === 0 ? (
        <p><em>No messages available</em></p>
      ) : (
        <div style={{ maxHeight: '600px', overflowY: 'auto', border: '1px solid #ccc', padding: '1rem', background: '#fafbfc' }}>
          {messages.map((msg: any, index: number) => {
            const isAgent = msg.author_id === 'ciris_agent' || msg.author_id === 'agent';
            return (
              <div
                key={msg.id || index}
                style={{
                  marginBottom: '1rem',
                  paddingBottom: '1rem',
                  borderBottom: '1px solid #eee',
                  background: isAgent ? '#e8f5e9' : '#e3eafc',
                  borderRadius: 4,
                  padding: 8,
                }}
              >
                <div style={{ fontSize: '0.9em', color: '#666', marginBottom: '0.5rem' }}>
                  <strong>{isAgent ? 'Agent' : 'User'}:</strong> {msg.author_name || msg.author_id} | <strong>Time:</strong> {formatTime(msg.timestamp)}
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>
      )}
    </div>
  );
}
