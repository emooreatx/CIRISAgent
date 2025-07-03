'use client';

import { useQuery } from '@tanstack/react-query';
import { cirisClient } from '../lib/ciris-sdk';
import { useAuth } from '../contexts/AuthContext';
import Link from 'next/link';

export default function Home() {
  const { user } = useAuth();
  const { data: status } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => cirisClient.agent.getStatus(),
  });

  const { data: identity } = useQuery({
    queryKey: ['agent-identity'],
    queryFn: () => cirisClient.agent.getIdentity(),
  });

  const { data: runtimeState } = useQuery({
    queryKey: ['runtime-state'],
    queryFn: () => cirisClient.system.getRuntimeState(),
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
                <dd className="mt-1 text-sm text-gray-900">{status.agent_id}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">State</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${
                    runtimeState?.processor_state === 'paused' 
                      ? 'bg-yellow-100 text-yellow-800' 
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {status.cognitive_state} {runtimeState?.processor_state === 'paused' && '(Paused)'}
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
                <dd className="mt-1 text-sm text-gray-900 capitalize">{runtimeState?.processor_state || 'Unknown'}</dd>
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
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Permissions</h3>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {identity.permissions?.map((permission: string) => (
                    <div key={permission} className="flex items-center">
                      <svg className="text-blue-500 mr-2" width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      <span className="text-sm text-gray-700">{permission.replace(/_/g, ' ').toLowerCase()}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Active Handlers ({identity.handlers?.length || 0})</h3>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {identity.handlers?.map((handler: string) => {
                    const handlerName = handler.replace('Handler', '').replace(/([A-Z])/g, ' $1').trim();
                    const isExternal = handler.toLowerCase().includes('speak') || handler.toLowerCase().includes('observe');
                    const isInternal = handler.toLowerCase().includes('ponder') || handler.toLowerCase().includes('recall');
                    const isSystem = handler.toLowerCase().includes('task') || handler.toLowerCase().includes('defer');
                    
                    return (
                      <div key={handler} className="flex items-start">
                        <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                          isExternal ? 'bg-blue-100 text-blue-700' :
                          isInternal ? 'bg-purple-100 text-purple-700' :
                          isSystem ? 'bg-amber-100 text-amber-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {handlerName}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 text-xs text-gray-500">
                  <span className="inline-flex items-center mr-4">
                    <span className="w-2 h-2 bg-blue-400 rounded-full mr-1"></span> External
                  </span>
                  <span className="inline-flex items-center mr-4">
                    <span className="w-2 h-2 bg-purple-400 rounded-full mr-1"></span> Internal
                  </span>
                  <span className="inline-flex items-center">
                    <span className="w-2 h-2 bg-amber-400 rounded-full mr-1"></span> System
                  </span>
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
