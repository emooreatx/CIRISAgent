'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';
import { useAuth } from '../../contexts/AuthContext';
import toast from 'react-hot-toast';
import { InfoIcon, ExclamationTriangleIcon, StatusDot } from '../../components/Icons';

export default function SystemPage() {
  const { hasRole } = useAuth();
  const queryClient = useQueryClient();
  const [confirmDialog, setConfirmDialog] = useState<{ type: string; name?: string } | null>(null);

  // Fetch system health
  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => cirisClient.system.getHealth(),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch services
  const { data: services } = useQuery({
    queryKey: ['system-services'],
    queryFn: () => cirisClient.system.getServices(),
    refetchInterval: 5000,
  });

  // Fetch resources
  const { data: resources } = useQuery({
    queryKey: ['system-resources'],
    queryFn: () => cirisClient.system.getResources(),
    refetchInterval: 5000,
  });

  // Fetch processors
  const { data: processors } = useQuery({
    queryKey: ['system-processors'],
    queryFn: () => cirisClient.system.getProcessors(),
    refetchInterval: 5000,
    enabled: hasRole('ADMIN'),
  });

  // Fetch runtime status
  const { data: runtimeStatus } = useQuery({
    queryKey: ['system-runtime-status'],
    queryFn: () => cirisClient.system.getRuntimeStatus(),
    refetchInterval: 5000,
  });

  // Fetch adapters
  const { data: adapters } = useQuery({
    queryKey: ['system-adapters'],
    queryFn: () => cirisClient.system.getAdapters(),
    refetchInterval: 5000,
    enabled: hasRole('ADMIN'),
  });

  // Runtime control mutations
  const pauseMutation = useMutation({
    mutationFn: () => cirisClient.system.pauseRuntime(),
    onSuccess: () => {
      toast.success('Runtime paused');
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
    onError: () => {
      toast.error('Failed to pause runtime');
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => cirisClient.system.resumeRuntime(),
    onSuccess: () => {
      toast.success('Runtime resumed');
      queryClient.invalidateQueries({ queryKey: ['system-health'] });
    },
    onError: () => {
      toast.error('Failed to resume runtime');
    },
  });

  // Processor control mutations
  const pauseProcessorMutation = useMutation({
    mutationFn: ({ name, duration }: { name: string; duration?: number }) =>
      cirisClient.system.pauseProcessor(name, duration),
    onSuccess: (_, { name }) => {
      toast.success(`Processor ${name} paused`);
      queryClient.invalidateQueries({ queryKey: ['system-processors'] });
    },
    onError: (_, { name }) => {
      toast.error(`Failed to pause processor ${name}`);
    },
  });

  const resumeProcessorMutation = useMutation({
    mutationFn: (name: string) => cirisClient.system.resumeProcessor(name),
    onSuccess: (_, name) => {
      toast.success(`Processor ${name} resumed`);
      queryClient.invalidateQueries({ queryKey: ['system-processors'] });
    },
    onError: (_, name) => {
      toast.error(`Failed to resume processor ${name}`);
    },
  });

  // Adapter control mutations

  const reloadAdapterMutation = useMutation({
    mutationFn: (adapterId: string) => cirisClient.system.reloadAdapter(adapterId),
    onSuccess: (_, adapterId) => {
      toast.success(`Adapter ${adapterId} reloaded`);
      queryClient.invalidateQueries({ queryKey: ['system-adapters'] });
    },
    onError: (_, adapterId) => {
      toast.error(`Failed to reload adapter ${adapterId}`);
    },
  });

  const unregisterAdapterMutation = useMutation({
    mutationFn: (adapterId: string) => cirisClient.system.unregisterAdapter(adapterId),
    onSuccess: (_, adapterId) => {
      toast.success(`Adapter ${adapterId} removed`);
      queryClient.invalidateQueries({ queryKey: ['system-adapters'] });
    },
    onError: (_, adapterId) => {
      toast.error(`Failed to remove adapter ${adapterId}`);
    },
  });

  const registerAdapterMutation = useMutation({
    mutationFn: (adapterType: string) => cirisClient.system.registerAdapter(adapterType),
    onSuccess: (_, adapterType) => {
      toast.success(`${adapterType} adapter registered`);
      queryClient.invalidateQueries({ queryKey: ['system-adapters'] });
    },
    onError: (_, adapterType) => {
      toast.error(`Failed to register ${adapterType} adapter`);
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

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'green';
      case 'degraded':
        return 'yellow';
      case 'unhealthy':
        return 'red';
      default:
        return 'gray';
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return '✓';
      case 'degraded':
        return '!';
      case 'unhealthy':
        return '✗';
      default:
        return '?';
    }
  };

  const handleConfirmAction = () => {
    if (!confirmDialog) return;

    switch (confirmDialog.type) {
      case 'pauseRuntime':
        pauseMutation.mutate();
        break;
      case 'resumeRuntime':
        resumeMutation.mutate();
        break;
      case 'pauseProcessor':
        if (confirmDialog.name) {
          pauseProcessorMutation.mutate({ name: confirmDialog.name });
        }
        break;
      case 'resumeProcessor':
        if (confirmDialog.name) {
          resumeProcessorMutation.mutate(confirmDialog.name);
        }
        break;
      case 'reloadAdapter':
        if (confirmDialog.name) {
          reloadAdapterMutation.mutate(confirmDialog.name);
        }
        break;
      case 'unregisterAdapter':
        if (confirmDialog.name) {
          unregisterAdapterMutation.mutate(confirmDialog.name);
        }
        break;
      case 'registerAdapter':
        if (confirmDialog.name) {
          registerAdapterMutation.mutate(confirmDialog.name);
        }
        break;
    }
    setConfirmDialog(null);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white shadow">
        <div className="px-4 py-5 sm:px-6">
          <h2 className="text-2xl font-bold text-gray-900">System Status</h2>
          <p className="mt-1 text-sm text-gray-500">
            Comprehensive system health monitoring and runtime control
          </p>
        </div>
      </div>

      {/* Overall System Health */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">System Overview</h3>
          
          {health && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Overall Health</dt>
                <dd className="mt-2 flex items-center">
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-lg font-semibold bg-${getHealthColor(health.status)}-100 text-${getHealthColor(health.status)}-800`}>
                    <span className="mr-2">{getHealthIcon(health.status)}</span>
                    {health.status?.toUpperCase()}
                  </span>
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Uptime</dt>
                <dd className="mt-2 text-2xl font-semibold text-gray-900">
                  {health.uptime_seconds ? formatUptime(health.uptime_seconds) : 'N/A'}
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Memory Usage</dt>
                <dd className="mt-2 text-2xl font-semibold text-gray-900">
                  {resources?.memory_mb ? `${resources.memory_mb} MB` : 'N/A'}
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">CPU Usage</dt>
                <dd className="mt-2 text-2xl font-semibold text-gray-900">
                  {resources?.cpu_percent ? `${resources.cpu_percent}%` : 'N/A'}
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
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setConfirmDialog({ type: 'pauseRuntime' })}
                disabled={pauseMutation.isPending || runtimeStatus?.is_paused}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-yellow-600 hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg className="mr-2 -ml-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {pauseMutation.isPending ? 'Pausing...' : 'Pause Runtime'}
              </button>
              
              <button
                onClick={() => setConfirmDialog({ type: 'resumeRuntime' })}
                disabled={resumeMutation.isPending || !runtimeStatus?.is_paused}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg className="mr-2 -ml-1 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {resumeMutation.isPending ? 'Resuming...' : 'Resume Runtime'}
              </button>
              
              {runtimeStatus?.is_paused && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800">
                  <InfoIcon className="mr-1.5" size="sm" />
                  Runtime Paused
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Resource Usage */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Resource Usage</h3>
          
          {resources ? (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">CPU Usage</span>
                  <span className={`text-lg font-bold ${resources?.cpu_percent > 80 ? 'text-red-600' : resources?.cpu_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                    {resources?.cpu_percent?.toFixed(1) || 0}%
                  </span>
                </div>
                <div className="relative">
                  <div className="overflow-hidden h-4 text-xs flex rounded-full bg-gray-200">
                    <div
                      style={{ width: `${resources?.cpu_percent || 0}%` }}
                      className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-300 ${
                        resources?.cpu_percent > 80 ? 'bg-red-500' : resources?.cpu_percent > 60 ? 'bg-yellow-500' : 'bg-blue-500'
                      }`}
                    />
                  </div>
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">Memory Usage</span>
                  <span className={`text-lg font-bold ${resources?.memory_percent > 80 ? 'text-red-600' : resources?.memory_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                    {resources?.memory_mb || 0} MB
                  </span>
                </div>
                <div className="relative">
                  <div className="overflow-hidden h-4 text-xs flex rounded-full bg-gray-200">
                    <div
                      style={{ width: `${resources?.memory_percent || 0}%` }}
                      className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-300 ${
                        resources?.memory_percent > 80 ? 'bg-red-500' : resources?.memory_percent > 60 ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                    />
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  {resources?.memory_percent?.toFixed(1) || 0}% utilized
                </p>
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">Disk Usage</span>
                  <span className="text-lg font-bold text-green-600">
                    {resources?.disk_usage_gb ? `${resources.disk_usage_gb} GB` : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500">Loading resource information...</p>
            </div>
          )}
        </div>
      </div>

      {/* Services Status - Grid View */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Services Health (19 Services)</h3>
            <div className="flex items-center space-x-4 text-sm">
              <span className="flex items-center">
                <StatusDot status="green" className="mr-1" />
                Healthy
              </span>
              <span className="flex items-center">
                <StatusDot status="yellow" className="mr-1" />
                Degraded
              </span>
              <span className="flex items-center">
                <StatusDot status="red" className="mr-1" />
                Unhealthy
              </span>
            </div>
          </div>
          
          {services?.services ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {services.services.map((service: any) => (
                <div
                  key={service.name}
                  className={`relative p-4 rounded-lg border-2 transition-all duration-200 hover:shadow-md ${
                    service.status === 'healthy'
                      ? 'border-green-200 bg-green-50 hover:border-green-300'
                      : service.status === 'degraded'
                      ? 'border-yellow-200 bg-yellow-50 hover:border-yellow-300'
                      : 'border-red-200 bg-red-50 hover:border-red-300'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-gray-900 truncate">
                        {service.name}
                      </h4>
                      <p className="text-xs text-gray-500 mt-1">
                        {service.service_type}
                      </p>
                    </div>
                    <StatusDot
                      status={service.status === 'healthy' ? 'green' : service.status === 'degraded' ? 'yellow' : 'red'}
                      className="flex-shrink-0 ml-2"
                    />
                  </div>
                  {service.capabilities && service.capabilities.length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs text-gray-600" title={service.capabilities.join(', ')}>
                        {service.capabilities.length} capabilities
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500">Loading services information...</p>
            </div>
          )}
        </div>
      </div>

      {/* Processor Management */}
      {hasRole('ADMIN') && processors && processors.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Processor Management</h3>
            
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
              <table className="min-w-full divide-y divide-gray-300">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Processor Name
                    </th>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Status
                    </th>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      State
                    </th>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Pause Expires
                    </th>
                    <th scope="col" className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {processors.map((processor: any) => (
                    <tr key={processor.name}>
                      <td className="whitespace-nowrap px-3 py-4 text-sm font-medium text-gray-900">
                        {processor.name}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm">
                        <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                          processor.is_paused
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {processor.is_paused ? 'Paused' : 'Running'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {processor.state || 'N/A'}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {processor.pause_expires_at ? new Date(processor.pause_expires_at).toLocaleString() : 'N/A'}
                      </td>
                      <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                        {processor.is_paused ? (
                          <button
                            onClick={() => setConfirmDialog({ type: 'resumeProcessor', name: processor.name })}
                            className="text-green-600 hover:text-green-900"
                          >
                            Resume
                          </button>
                        ) : (
                          <button
                            onClick={() => setConfirmDialog({ type: 'pauseProcessor', name: processor.name })}
                            className="text-yellow-600 hover:text-yellow-900"
                          >
                            Pause
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Adapter Registration */}
      {hasRole('ADMIN') && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Register New Adapter</h3>
            <div className="flex items-center space-x-4">
              <select
                onChange={(e) => {
                  if (e.target.value) {
                    setConfirmDialog({ type: 'registerAdapter', name: e.target.value });
                    e.target.value = '';
                  }
                }}
                className="block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="">Select adapter type...</option>
                <option value="discord">Discord</option>
                <option value="slack">Slack</option>
                <option value="api">API</option>
                <option value="cli">CLI</option>
                <option value="webhook">Webhook</option>
              </select>
              <p className="text-sm text-gray-500">
                Select an adapter type to register a new instance
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Adapter Management */}
      {hasRole('ADMIN') && adapters?.adapters && adapters.adapters.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Adapter Management</h3>
            
            <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
              <table className="min-w-full divide-y divide-gray-300">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Adapter Name
                    </th>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Type
                    </th>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Status
                    </th>
                    <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Active Channels
                    </th>
                    <th scope="col" className="relative py-3.5 pl-3 pr-4 sm:pr-6">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {adapters.adapters.map((adapter: any) => (
                    <tr key={adapter.adapter_id}>
                      <td className="whitespace-nowrap px-3 py-4 text-sm font-medium text-gray-900">
                        {adapter.adapter_id}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {adapter.adapter_type}
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm">
                        <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                          adapter.is_running
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {adapter.is_running ? 'Running' : 'Stopped'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        {adapter.channels?.length || 0}
                      </td>
                      <td className="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                        <div className="flex items-center justify-end space-x-3">
                          <button
                            onClick={() => setConfirmDialog({ type: 'reloadAdapter', name: adapter.adapter_id })}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            Reload
                          </button>
                          <button
                            onClick={() => setConfirmDialog({ type: 'unregisterAdapter', name: adapter.adapter_id })}
                            className="text-red-600 hover:text-red-900"
                          >
                            Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Dialog */}
      {confirmDialog && (
        <div className="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true"></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div className="sm:flex sm:items-start">
                <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-yellow-100 sm:mx-0 sm:h-10 sm:w-10">
                  <ExclamationTriangleIcon className="text-yellow-600" size="lg" />
                </div>
                <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Confirm Action
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      {confirmDialog.type.includes('pause') 
                        ? `Are you sure you want to pause ${confirmDialog.name || 'the runtime'}? This will temporarily stop processing.`
                        : `Are you sure you want to resume ${confirmDialog.name || 'the runtime'}?`}
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                <button
                  type="button"
                  onClick={handleConfirmAction}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-yellow-600 text-base font-medium text-white hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Confirm
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDialog(null)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}