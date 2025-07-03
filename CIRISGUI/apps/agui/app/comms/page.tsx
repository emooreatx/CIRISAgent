'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';
import toast from 'react-hot-toast';

export default function CommsPage() {
  const [message, setMessage] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();

  // Fetch conversation history - limit to 20 most recent
  const { data: history, isLoading } = useQuery({
    queryKey: ['conversation-history'],
    queryFn: async () => {
      const result = await cirisClient.agent.getHistory({
        channel_id: 'api_0.0.0.0_8080',
        limit: 20
      });
      return result;
    },
    refetchInterval: 2000, // Refresh every 2 seconds to catch responses
  });

  // Fetch agent status
  const { data: status } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => cirisClient.agent.getStatus(),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Send message mutation
  const sendMessage = useMutation({
    mutationFn: async (msg: string) => {
      const response = await cirisClient.agent.interact(msg, {
        channel_id: 'api_0.0.0.0_8080'
      });
      return response;
    },
    onSuccess: (response) => {
      setMessage('');
      // Immediately refetch history to show the response
      queryClient.invalidateQueries({ queryKey: ['conversation-history'] });
      
      // Show the agent's response in a toast for visibility
      if (response.response) {
        toast.success(`Agent: ${response.response}`, { duration: 5000 });
      }
    },
    onError: (error: any) => {
      console.error('Send message error:', error);
      toast.error(error.message || 'Failed to send message');
    },
  });

  // WebSocket connection (currently disabled as it's not working with the SDK yet)
  useEffect(() => {
    // TODO: Implement WebSocket support in the SDK
    setWsConnected(false);
  }, []);

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

  // Get messages and ensure proper order (oldest to newest)
  const messages = useMemo(() => {
    if (!history?.messages) return [];
    
    // Sort by timestamp (oldest first) and take last 20
    return [...history.messages]
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .slice(-20);
  }, [history]);

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
            ) : messages.length === 0 ? (
              <div className="text-center text-gray-500">No messages yet. Start a conversation!</div>
            ) : (
              <div className="space-y-3">
                {messages.map((msg, idx) => {
                  // Debug log to see message structure
                  if (idx === 0) console.log('Message structure:', msg);
                  
                  return (
                    <div
                      key={msg.id || idx}
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
                          {msg.author || msg.author_name || (msg.is_agent ? 'CIRIS' : 'You')} • {new Date(msg.timestamp).toLocaleTimeString()}
                        </div>
                        <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <div className="text-xs text-gray-500 mb-2">
            Showing last 20 messages
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

      {/* Debug info */}
      {process.env.NODE_ENV === 'development' && (
        <div className="mt-4 p-4 bg-gray-100 rounded text-xs">
          <p>Total messages in history: {history?.total_count || 0}</p>
          <p>Showing: {messages.length} messages</p>
          <p>Channel: api_0.0.0.0_8080</p>
        </div>
      )}
    </div>
  );
}