'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../lib/api-client';
import { useAuth } from '../../contexts/AuthContext';
import toast from 'react-hot-toast';

export default function SystemPage() {
  const { hasRole } = useAuth();
  const queryClient = useQueryClient();

  // Fetch system health
  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch services
  const { data: services } = useQuery({
    queryKey: ['system-services'],
    queryFn: () => apiClient.getServices(),
    refetchInterval: 10000,
  });

  // Fetch resources
  const { data: resources } = useQuery({
    queryKey: ['system-resources'],
    queryFn: () => apiClient.getResources(),
    refetchInterval: 5000,
  });

  // Runtime control mutations
  const pauseMutation = useMutation({
    mutationFn: () => apiClient.pauseRuntime(),
    onSuccess: () => {
      toast.success('Runtime paused');
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
    onError: () => {
      toast.error('Failed to pause runtime');
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => apiClient.resumeRuntime(),
    onSuccess: () => {
      toast.success('Runtime resumed');
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
    onError: () => {
      toast.error('Failed to resume runtime');
    },
  });

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  const formatBytes = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* System Health */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">System Health</h3>
          
          {health && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg">
                <dt className="text-sm font-medium text-gray-500">Status</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">
                  <span className={`inline-flex items-center rounded-md px-2 py-1 text-sm font-medium ${
                    health.status === 'healthy' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {health.status}
                  </span>
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg">
                <dt className="text-sm font-medium text-gray-500">Uptime</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">
                  {health.uptime ? formatUptime(health.uptime) : 'N/A'}
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg">
                <dt className="text-sm font-medium text-gray-500">Version</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">
                  {health.version || 'Unknown'}
                </dd>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Runtime Control */}
      {hasRole('ADMIN') && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Runtime Control</h3>
            <div className="flex space-x-3">
              <button
                onClick={() => pauseMutation.mutate()}
                disabled={pauseMutation.isPending || health?.is_paused}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-yellow-600 hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 disabled:opacity-50"
              >
                {pauseMutation.isPending ? 'Pausing...' : 'Pause Runtime'}
              </button>
              
              <button
                onClick={() => resumeMutation.mutate()}
                disabled={resumeMutation.isPending || !health?.is_paused}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
              >
                {resumeMutation.isPending ? 'Resuming...' : 'Resume Runtime'}
              </button>
            </div>
            
            {health?.is_paused && (
              <p className="mt-2 text-sm text-orange-600">
                Runtime is currently paused. The agent will not process new messages.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Resource Usage */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Resource Usage</h3>
          
          {resources && (
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">CPU Usage</span>
                  <span className="font-medium">{resources.cpu_percent?.toFixed(1)}%</span>
                </div>
                <div className="mt-1 relative pt-1">
                  <div className="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
                    <div
                      style={{ width: `${resources.cpu_percent}%` }}
                      className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-blue-500"
                    />
                  </div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Memory Usage</span>
                  <span className="font-medium">
                    {formatBytes(resources.memory_used)} / {formatBytes(resources.memory_total)}
                  </span>
                </div>
                <div className="mt-1 relative pt-1">
                  <div className="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
                    <div
                      style={{ width: `${(resources.memory_used / resources.memory_total) * 100}%` }}
                      className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-green-500"
                    />
                  </div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Disk Usage</span>
                  <span className="font-medium">
                    {formatBytes(resources.disk_used)} / {formatBytes(resources.disk_total)}
                  </span>
                </div>
                <div className="mt-1 relative pt-1">
                  <div className="overflow-hidden h-2 text-xs flex rounded bg-gray-200">
                    <div
                      style={{ width: `${(resources.disk_used / resources.disk_total) * 100}%` }}
                      className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-purple-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Services Status */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Services Status</h3>
          
          <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
            <table className="min-w-full divide-y divide-gray-300">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Service
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Type
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Capabilities
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {services?.map((service: any) => (
                  <tr key={service.name}>
                    <td className="whitespace-nowrap px-3 py-4 text-sm font-medium text-gray-900">
                      {service.name}
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                      {service.service_type}
                    </td>
                    <td className="whitespace-nowrap px-3 py-4 text-sm">
                      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                        service.status === 'healthy' 
                          ? 'bg-green-50 text-green-700 ring-green-600/20' 
                          : service.status === 'degraded'
                          ? 'bg-yellow-50 text-yellow-700 ring-yellow-600/20'
                          : 'bg-red-50 text-red-700 ring-red-600/20'
                      }`}>
                        {service.status}
                      </span>
                    </td>
                    <td className="px-3 py-4 text-sm text-gray-500">
                      <div className="max-w-xs truncate">
                        {service.capabilities?.join(', ') || 'None'}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}