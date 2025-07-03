'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';
import { format } from 'date-fns';
import { ArrowDownTrayIcon, FunnelIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

interface AuditEntry {
  id?: string;
  timestamp: string;
  service: string;
  action: string;
  user_id?: string;
  actor?: string;
  details?: any;
  result?: string;
  status?: string;
  severity?: 'info' | 'warning' | 'error' | 'critical';
}

interface AuditFilter {
  start_time?: string;
  end_time?: string;
  service?: string;
  action?: string;
  limit: number;
}

export default function AuditPage() {
  const [filters, setFilters] = useState<AuditFilter>({ limit: 100 });
  const [isExporting, setIsExporting] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  
  // Set default date range to last 7 days
  const defaultEndDate = new Date();
  const defaultStartDate = new Date();
  defaultStartDate.setDate(defaultStartDate.getDate() - 7);

  // Fetch audit trail
  const { data, isLoading, refetch, error } = useQuery({
    queryKey: ['audit-trail', filters],
    queryFn: () => cirisClient.audit.getEntries({
      page_size: filters.limit,
      service: filters.service,
      // Note: The API might expect different parameter names for time filtering
      // We may need to adjust these based on the actual API
    }),
    retry: 1,
  });

  // Extract entries from paginated response
  const entries = data?.items || [];

  const actionTypes = [
    'all',
    'auth.login',
    'auth.logout',
    'auth.token_refresh',
    'config.update',
    'config.backup',
    'config.restore',
    'runtime.pause',
    'runtime.resume',
    'agent.interact',
    'agent.startup',
    'agent.shutdown',
    'memory.query',
    'memory.store',
    'deferral.create',
    'deferral.resolve',
    'emergency.shutdown',
    'adapter.pause',
    'adapter.resume',
    'processor.pause',
    'processor.resume',
  ];
  
  const services = [
    'all',
    'auth',
    'agent',
    'memory',
    'config',
    'runtime',
    'telemetry',
    'audit',
    'wise_authority',
    'api_adapter',
    'discord_adapter',
    'cli_adapter',
  ];

  const handleFilterChange = (key: keyof AuditFilter, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
    }));
  };
  
  const handleExport = async () => {
    setIsExporting(true);
    try {
      // Use search API to get entries for export
      const exportData = await cirisClient.audit.searchEntries({
        start_date: filters.start_time,
        end_date: filters.end_time,
        service: filters.service,
        page_size: 1000 // Export up to 1000 entries
      });
      // Create and download CSV file
      const csv = convertToCSV(exportData.items || []);
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_export_${format(new Date(), 'yyyy-MM-dd_HH-mm-ss')}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };
  
  const convertToCSV = (entries: AuditEntry[]) => {
    const headers = ['Timestamp', 'Service', 'Action', 'User/Actor', 'Details', 'Status', 'Result'];
    const rows = entries.map(entry => [
      entry.timestamp,
      entry.service || '',
      entry.action || '',
      entry.user_id || entry.actor || 'System',
      JSON.stringify(entry.details || {}),
      entry.status || '',
      entry.result || 'success'
    ]);
    
    return [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');
  };
  
  const getSeverityColor = (entry: AuditEntry) => {
    // Determine severity based on action and result
    if (entry.result === 'error' || entry.status === 'error') {
      return 'bg-red-50 text-red-700 ring-red-600/20';
    }
    if (entry.action?.includes('emergency') || entry.action?.includes('shutdown')) {
      return 'bg-red-50 text-red-700 ring-red-600/20';
    }
    if (entry.action?.includes('config') || entry.action?.includes('restore')) {
      return 'bg-amber-50 text-amber-700 ring-amber-600/20';
    }
    if (entry.action?.includes('auth') && entry.result === 'failure') {
      return 'bg-orange-50 text-orange-700 ring-orange-600/20';
    }
    if (entry.action?.includes('pause') || entry.action?.includes('resume')) {
      return 'bg-blue-50 text-blue-700 ring-blue-600/20';
    }
    return 'bg-gray-50 text-gray-700 ring-gray-600/20';
  };
  
  const getActionBadgeColor = (action: string) => {
    if (action?.includes('login') || action?.includes('logout')) {
      return 'bg-indigo-50 text-indigo-700 ring-indigo-700/10';
    }
    if (action?.includes('config')) {
      return 'bg-amber-50 text-amber-700 ring-amber-700/10';
    }
    if (action?.includes('emergency') || action?.includes('shutdown')) {
      return 'bg-red-50 text-red-700 ring-red-700/10';
    }
    if (action?.includes('pause') || action?.includes('resume')) {
      return 'bg-blue-50 text-blue-700 ring-blue-700/10';
    }
    if (action?.includes('memory')) {
      return 'bg-purple-50 text-purple-700 ring-purple-700/10';
    }
    if (action?.includes('deferral')) {
      return 'bg-green-50 text-green-700 ring-green-700/10';
    }
    return 'bg-gray-50 text-gray-700 ring-gray-700/10';
  };

  return (
    <div className="max-w-7xl mx-auto">
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-medium text-gray-900">
              System Audit Trail
            </h3>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                <FunnelIcon className="h-4 w-4 mr-2" />
                {showFilters ? 'Hide' : 'Show'} Filters
              </button>
              <button
                onClick={handleExport}
                disabled={isExporting || !entries?.length}
                className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                {isExporting ? 'Exporting...' : 'Export CSV'}
              </button>
              <button
                onClick={() => refetch()}
                disabled={isLoading}
                className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                <ArrowPathIcon className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
          </div>

          {/* Filters */}
          {showFilters && (
            <div className="mb-6 bg-gray-50 p-4 rounded-lg border border-gray-200">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {/* Date Range */}
                <div>
                  <label htmlFor="start_time" className="block text-sm font-medium text-gray-700">
                    Start Date
                  </label>
                  <input
                    type="datetime-local"
                    id="start_time"
                    value={filters.start_time ? filters.start_time.slice(0, 16) : format(defaultStartDate, "yyyy-MM-dd'T'HH:mm")}
                    onChange={(e) => handleFilterChange('start_time', e.target.value ? new Date(e.target.value).toISOString() : undefined)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>
                
                <div>
                  <label htmlFor="end_time" className="block text-sm font-medium text-gray-700">
                    End Date
                  </label>
                  <input
                    type="datetime-local"
                    id="end_time"
                    value={filters.end_time ? filters.end_time.slice(0, 16) : format(defaultEndDate, "yyyy-MM-dd'T'HH:mm")}
                    onChange={(e) => handleFilterChange('end_time', e.target.value ? new Date(e.target.value).toISOString() : undefined)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  />
                </div>

                {/* Service Filter */}
                <div>
                  <label htmlFor="service" className="block text-sm font-medium text-gray-700">
                    Service
                  </label>
                  <select
                    id="service"
                    value={filters.service || 'all'}
                    onChange={(e) => handleFilterChange('service', e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  >
                    {services.map(service => (
                      <option key={service} value={service}>
                        {service === 'all' ? 'All Services' : service}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Action Filter */}
                <div>
                  <label htmlFor="action" className="block text-sm font-medium text-gray-700">
                    Action
                  </label>
                  <select
                    id="action"
                    value={filters.action || 'all'}
                    onChange={(e) => handleFilterChange('action', e.target.value)}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                  >
                    {actionTypes.map(type => (
                      <option key={type} value={type}>
                        {type === 'all' ? 'All Actions' : type}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Limit */}
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
                    <option value={1000}>1000 entries</option>
                  </select>
                </div>
              </div>
              
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => {
                    setFilters({ limit: 100 });
                    refetch();
                  }}
                  className="mr-3 inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Clear Filters
                </button>
              </div>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-4">
              <div className="flex">
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Error loading audit trail</h3>
                  <div className="mt-2 text-sm text-red-700">
                    <p>{(error as any)?.message || 'Failed to fetch audit entries'}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Audit entries table */}
          <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
            <table className="min-w-full divide-y divide-gray-300">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Timestamp
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Service
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Action
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    User/Actor
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Details
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-gray-500">
                      <div className="inline-flex items-center">
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Loading audit entries...
                      </div>
                    </td>
                  </tr>
                ) : entries?.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-gray-500">
                      <div>
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                        </svg>
                        <p className="mt-2 text-sm">No audit entries found</p>
                        <p className="mt-1 text-xs text-gray-400">Try adjusting your filters</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  entries?.map((entry: AuditEntry, idx: number) => (
                    <tr key={entry.id || idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        <div className="flex flex-col">
                          <span className="font-medium">
                            {format(new Date(entry.timestamp), 'MMM dd, yyyy')}
                          </span>
                          <span className="text-xs text-gray-500">
                            {format(new Date(entry.timestamp), 'HH:mm:ss.SSS')}
                          </span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        <span className="font-medium">
                          {entry.service || 'unknown'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${getActionBadgeColor(entry.action)}`}>
                          {entry.action || entry.action || 'unknown'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-900">
                        <div className="flex items-center">
                          <span className="font-medium">
                            {entry.user_id || entry.actor || 'System'}
                          </span>
                          {entry.user_id && entry.user_id !== 'System' && (
                            <span className="ml-1 text-xs text-gray-500">
                              (User)
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-4 text-sm text-gray-500">
                        {entry.details ? (
                          <details className="cursor-pointer">
                            <summary className="text-xs">
                              <span className="hover:text-gray-700">View details</span>
                            </summary>
                            <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-x-auto max-w-md">
                              {JSON.stringify(entry.details, null, 2)}
                            </pre>
                          </details>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm">
                        <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${getSeverityColor(entry)}`}>
                          {entry.result || entry.status || 'success'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination info */}
          {entries && entries.length > 0 && (
            <div className="mt-4 flex items-center justify-between text-sm text-gray-700">
              <div>
                Showing <span className="font-medium">{entries.length}</span> entries
                {data?.total && data.total > entries.length && (
                  <span className="text-gray-500"> of {data.total} total</span>
                )}
              </div>
              {data?.has_next && (
                <div className="text-gray-500">
                  There are more entries. Increase the limit or narrow your filters.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
