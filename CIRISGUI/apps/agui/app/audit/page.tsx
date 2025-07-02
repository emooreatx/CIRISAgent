'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../lib/api-client';

interface AuditFilter {
  action_type?: string;
  user_id?: string;
  limit: number;
}

export default function AuditPage() {
  const [filters, setFilters] = useState<AuditFilter>({ limit: 100 });

  // Fetch audit trail
  const { data: entries, isLoading, refetch } = useQuery({
    queryKey: ['audit-trail', filters],
    queryFn: () => apiClient.getAuditTrail(filters),
  });

  const actionTypes = [
    'all',
    'auth.login',
    'auth.logout',
    'config.update',
    'runtime.pause',
    'runtime.resume',
    'message.send',
    'deferral.resolve',
  ];

  const handleFilterChange = (key: keyof AuditFilter, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
    }));
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Audit Trail
          </h3>

          {/* Filters */}
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="action_type" className="block text-sm font-medium text-gray-700">
                Action Type
              </label>
              <select
                id="action_type"
                value={filters.action_type || 'all'}
                onChange={(e) => handleFilterChange('action_type', e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                {actionTypes.map(type => (
                  <option key={type} value={type}>
                    {type === 'all' ? 'All Actions' : type}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="user_id" className="block text-sm font-medium text-gray-700">
                User ID
              </label>
              <input
                type="text"
                id="user_id"
                value={filters.user_id || ''}
                onChange={(e) => handleFilterChange('user_id', e.target.value || undefined)}
                placeholder="Filter by user ID"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              />
            </div>

            <div>
              <label htmlFor="limit" className="block text-sm font-medium text-gray-700">
                Limit
              </label>
              <select
                id="limit"
                value={filters.limit}
                onChange={(e) => handleFilterChange('limit', parseInt(e.target.value))}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value={50}>50 entries</option>
                <option value={100}>100 entries</option>
                <option value={200}>200 entries</option>
                <option value={500}>500 entries</option>
              </select>
            </div>
          </div>

          <button
            onClick={() => refetch()}
            className="mb-4 inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Refresh
          </button>

          {/* Audit entries table */}
          <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
            <table className="min-w-full divide-y divide-gray-300">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Timestamp
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Action
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    User
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Details
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Result
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {isLoading ? (
                  <tr>
                    <td colSpan={5} className="text-center py-4 text-gray-500">
                      Loading audit entries...
                    </td>
                  </tr>
                ) : entries?.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-4 text-gray-500">
                      No audit entries found
                    </td>
                  </tr>
                ) : (
                  entries?.map((entry: any, idx: number) => (
                    <tr key={entry.id || idx}>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                          {entry.action_type}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        {entry.user_id || 'System'}
                      </td>
                      <td className="px-3 py-4 text-sm text-gray-500">
                        <div className="max-w-xs truncate" title={JSON.stringify(entry.details)}>
                          {entry.details ? JSON.stringify(entry.details) : '-'}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm">
                        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                          entry.result === 'success' 
                            ? 'bg-green-50 text-green-700 ring-green-600/20' 
                            : 'bg-red-50 text-red-700 ring-red-600/20'
                        }`}>
                          {entry.result || 'success'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
