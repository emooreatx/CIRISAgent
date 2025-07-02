'use client';

import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../lib/api-client-v1';
import toast from 'react-hot-toast';

export default function CommsPage() {
  const [message, setMessage] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();

  // Fetch conversation history
  const { data: history, isLoading } = useQuery({
    queryKey: ['conversation-history'],
    queryFn: () => apiClient.getHistory('api_0.0.0.0_8080', 100),
  });

  // Fetch agent status
  const { data: status } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => apiClient.getStatus(),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Send message mutation
  const sendMessage = useMutation({
    mutationFn: (msg: string) => apiClient.interact(msg, 'api_0.0.0.0_8080'),
    onSuccess: () => {
      setMessage('');
      queryClient.invalidateQueries({ queryKey: ['conversation-history'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send message');
    },
  });

  // Setup WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const ws = apiClient.connectWebSocket();
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
          // Subscribe to messages channel
          ws.send(JSON.stringify({ type: 'subscribe', channel: 'messages' }));
        };

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'message') {
            // Refresh conversation history when new message arrives
            queryClient.invalidateQueries({ queryKey: ['conversation-history'] });
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          // Reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [queryClient]);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim()) {
      sendMessage.mutate(message.trim());
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Agent Communications
            </h3>
            <div className="flex items-center space-x-4 text-sm">
              <span className={`flex items-center ${wsConnected ? 'text-green-600' : 'text-red-600'}`}>
                <div className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-600' : 'bg-red-600'}`} />
                {wsConnected ? 'Connected' : 'Disconnected'}
              </span>
              {status && (
                <span className="text-gray-600">
                  State: <span className="font-medium">{status.cognitive_state}</span>
                </span>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="border rounded-lg bg-gray-50 h-96 overflow-y-auto p-4 mb-4">
            {isLoading ? (
              <div className="text-center text-gray-500">Loading conversation...</div>
            ) : !history?.messages || history.messages.length === 0 ? (
              <div className="text-center text-gray-500">No messages yet. Start a conversation!</div>
            ) : (
              <div className="space-y-3">
                {history.messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.is_agent ? 'justify-start' : 'justify-end'}`}
                  >
                    <div
                      className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                        msg.is_agent
                          ? 'bg-white border border-gray-200'
                          : 'bg-blue-600 text-white'
                      }`}
                    >
                      <div className={`text-xs mb-1 ${msg.is_agent ? 'text-gray-500' : 'text-blue-100'}`}>
                        {msg.author} • {new Date(msg.timestamp).toLocaleTimeString()}
                      </div>
                      <div className="text-sm">{msg.content}</div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input form */}
          <form onSubmit={handleSubmit} className="flex space-x-3">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Type your message..."
              disabled={sendMessage.isPending || status?.is_paused}
              className="flex-1 min-w-0 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={sendMessage.isPending || !message.trim() || status?.is_paused}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sendMessage.isPending ? 'Sending...' : 'Send'}
            </button>
          </form>
          
          {status?.is_paused && (
            <div className="mt-2 text-sm text-orange-600">
              Agent is paused. Messages cannot be sent.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
