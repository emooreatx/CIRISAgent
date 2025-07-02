'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../lib/api-client-v1';
import { useAuth } from '../contexts/AuthContext';
import Link from 'next/link';

export default function Home() {
  const { user } = useAuth();
  const { data: status } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => apiClient.getStatus(),
  });

  const { data: identity } = useQuery({
    queryKey: ['agent-identity'],
    queryFn: () => apiClient.getIdentity(),
  });

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h1 className="text-2xl font-bold text-gray-900">Welcome to CIRIS GUI</h1>
          <p className="mt-2 text-gray-600">
            Agent Management Interface for the CIRIS Autonomous Agent System
          </p>
          {user && (
            <p className="mt-4 text-sm text-gray-500">
              Logged in as <span className="font-medium">{user.username || user.user_id}</span> ({user.role})
            </p>
          )}
        </div>
      </div>

      {/* Agent Status */}
      {status && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Agent Status</h2>
            <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-gray-500">Name</dt>
                <dd className="mt-1 text-sm text-gray-900">{status.name}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">State</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${
                    status.is_paused 
                      ? 'bg-yellow-100 text-yellow-800' 
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {status.cognitive_state} {status.is_paused && '(Paused)'}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Uptime</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {Math.floor(status.uptime_seconds / 3600)}h {Math.floor((status.uptime_seconds % 3600) / 60)}m
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Processor Status</dt>
                <dd className="mt-1 text-sm text-gray-900">{status.processor_status?.state || 'Unknown'}</dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* Agent Identity */}
      {identity && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Agent Identity</h2>
            <p className="text-sm text-gray-600 mb-4">{identity.purpose}</p>
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-gray-700">Capabilities</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {identity.capabilities?.map((capability: string) => (
                    <span key={capability} className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                      {capability}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Access</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Link href="/comms" className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500">
              <div className="flex-1 min-w-0">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="text-sm font-medium text-gray-900">Communications</p>
                <p className="text-sm text-gray-500 truncate">Chat with the agent</p>
              </div>
            </Link>

            <Link href="/system" className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500">
              <div className="flex-1 min-w-0">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="text-sm font-medium text-gray-900">System Status</p>
                <p className="text-sm text-gray-500 truncate">Monitor health & resources</p>
              </div>
            </Link>

            <Link href="/audit" className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500">
              <div className="flex-1 min-w-0">
                <span className="absolute inset-0" aria-hidden="true" />
                <p className="text-sm font-medium text-gray-900">Audit Trail</p>
                <p className="text-sm text-gray-500 truncate">View system activity</p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
