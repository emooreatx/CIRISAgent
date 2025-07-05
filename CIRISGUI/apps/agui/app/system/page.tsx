'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';
import { useAuth } from '../../contexts/AuthContext';
import toast from 'react-hot-toast';
import { 
  InfoIcon, 
  ExclamationTriangleIcon, 
  StatusDot, 
  GlobeIcon, 
  LightningBoltIcon, 
  CurrencyDollarIcon 
} from '../../components/Icons';

export default function SystemPage() {
  const { hasRole } = useAuth();
  const queryClient = useQueryClient();
  const [confirmDialog, setConfirmDialog] = useState<{ type: string; name?: string } | null>(null);
  const [adapterConfigModal, setAdapterConfigModal] = useState<{ type: string } | null>(null);
  const [adapterConfig, setAdapterConfig] = useState<any>({});

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
    queryFn: () => cirisClient.system.getProcessorStates(),
    refetchInterval: 5000,
    enabled: hasRole('ADMIN'),
  });

  // Fetch runtime state (more accurate than runtime status)
  const { data: runtimeState } = useQuery({
    queryKey: ['system-runtime-state'],
    queryFn: () => cirisClient.system.getRuntimeState(),
    refetchInterval: 5000,
  });
  
  // Map runtime state to runtime status for compatibility
  // Health data comes from v1/system/health which includes cognitive_state
  const healthData = health as any;
  const runtimeStatus = runtimeState ? {
    is_paused: runtimeState.processor_state === 'paused',
    cognitive_state: (runtimeState.cognitive_state !== 'UNKNOWN' ? runtimeState.cognitive_state : healthData?.cognitive_state?.toUpperCase()) || 'WORK',
    queue_depth: runtimeState.queue_depth,
    processor_status: runtimeState.processor_state
  } : null;

  // Fetch adapters
  const { data: adapters } = useQuery({
    queryKey: ['system-adapters'],
    queryFn: () => cirisClient.system.getAdapters(),
    refetchInterval: 5000,
    enabled: hasRole('ADMIN'),
  });
  
  // Fetch channels
  const { data: channels } = useQuery({
    queryKey: ['agent-channels'],
    queryFn: () => cirisClient.agent.getChannels(),
    refetchInterval: 5000,
  });
  
  // Fetch telemetry overview for environmental metrics
  const { data: telemetryOverview } = useQuery({
    queryKey: ['telemetry-overview'],
    queryFn: () => cirisClient.telemetry.getOverview(),
    refetchInterval: 30000,
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
    mutationFn: ({ adapterType, config }: { adapterType: string; config?: any }) => 
      cirisClient.system.registerAdapter(adapterType, config),
    onSuccess: (_, { adapterType }) => {
      toast.success(`${adapterType} adapter registered`);
      queryClient.invalidateQueries({ queryKey: ['system-adapters'] });
      queryClient.invalidateQueries({ queryKey: ['agent-channels'] });
      setAdapterConfigModal(null);
      setAdapterConfig({});
    },
    onError: (_, { adapterType }) => {
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
          registerAdapterMutation.mutate({ adapterType: confirmDialog.name });
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
                  {resources?.current_usage?.memory_mb ? `${resources.current_usage.memory_mb.toFixed(1)} MB` : 'N/A'}
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">CPU Usage</dt>
                <dd className="mt-2 text-2xl font-semibold text-gray-900">
                  {resources?.current_usage?.cpu_percent ? `${resources.current_usage.cpu_percent.toFixed(1)}%` : 'N/A'}
                </dd>
              </div>
            </div>
          )}
        </div>
      </div>


      {/* Resource Usage */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Resource Usage</h3>
          
          {resources ? (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">CPU Usage</span>
                  <span className={`text-lg font-bold ${resources?.current_usage?.cpu_percent > 80 ? 'text-red-600' : resources?.current_usage?.cpu_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                    {resources?.current_usage?.cpu_percent?.toFixed(1) || 0}%
                  </span>
                </div>
                <div className="relative">
                  <div className="overflow-hidden h-4 text-xs flex rounded-full bg-gray-200">
                    <div
                      style={{ width: `${resources?.current_usage?.cpu_percent || 0}%` }}
                      className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-300 ${
                        resources?.current_usage?.cpu_percent > 80 ? 'bg-red-500' : resources?.current_usage?.cpu_percent > 60 ? 'bg-yellow-500' : 'bg-blue-500'
                      }`}
                    />
                  </div>
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">Memory Usage</span>
                  <span className={`text-lg font-bold ${resources?.current_usage?.memory_percent > 80 ? 'text-red-600' : resources?.current_usage?.memory_percent > 60 ? 'text-yellow-600' : 'text-green-600'}`}>
                    {resources?.current_usage?.memory_mb ? resources.current_usage.memory_mb.toFixed(1) : 0} MB
                  </span>
                </div>
                <div className="relative">
                  <div className="overflow-hidden h-4 text-xs flex rounded-full bg-gray-200">
                    <div
                      style={{ width: `${resources?.current_usage?.memory_percent || 0}%` }}
                      className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-300 ${
                        resources?.current_usage?.memory_percent > 80 ? 'bg-red-500' : resources?.current_usage?.memory_percent > 60 ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                    />
                  </div>
                </div>
                <p className="text-xs text-gray-500">
                  {resources?.current_usage?.memory_percent?.toFixed(1) || 0}% utilized
                </p>
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-700">Disk Usage</span>
                  <span className="text-lg font-bold text-green-600">
                    {resources?.current_usage?.disk_used_mb ? `${(resources.current_usage.disk_used_mb / 1024).toFixed(1)} GB` : 'N/A'}
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

      {/* Environmental Impact */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Environmental Impact</h3>
          
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* CO2 Emissions */}
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">CO₂ Emissions</span>
                <GlobeIcon className="text-green-600" size="sm" />
              </div>
              <div className="space-y-2">
                <div>
                  <p className="text-2xl font-bold text-green-700">
                    {telemetryOverview?.carbon_per_hour_grams ? (telemetryOverview.carbon_per_hour_grams / 1000).toFixed(3) : '0.000'} kg
                  </p>
                  <p className="text-xs text-gray-600">Last hour</p>
                </div>
                <div className="pt-2 border-t border-green-200">
                  <p className="text-sm font-medium text-green-600">
                    {telemetryOverview?.carbon_per_hour_grams ? (telemetryOverview.carbon_per_hour_grams).toFixed(1) : '0.0'} g
                  </p>
                  <p className="text-xs text-gray-600">Per hour (actual)</p>
                </div>
              </div>
            </div>
            
            {/* Energy Usage */}
            <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Energy Usage</span>
                <LightningBoltIcon className="text-blue-600" size="sm" />
              </div>
              <div className="space-y-2">
                <div>
                  <p className="text-2xl font-bold text-blue-700">
                    {telemetryOverview?.energy_per_hour_kwh ? telemetryOverview.energy_per_hour_kwh.toFixed(4) : '0.0000'} kWh
                  </p>
                  <p className="text-xs text-gray-600">Last hour</p>
                </div>
                <div className="pt-2 border-t border-blue-200">
                  <p className="text-sm font-medium text-blue-600">
                    {telemetryOverview?.energy_per_hour_kwh ? (telemetryOverview.energy_per_hour_kwh * 1000).toFixed(1) : '0.0'} Wh
                  </p>
                  <p className="text-xs text-gray-600">Per hour (actual)</p>
                </div>
              </div>
            </div>
            
            {/* Cost */}
            <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">Estimated Cost</span>
                <CurrencyDollarIcon className="text-purple-600" size="sm" />
              </div>
              <div className="space-y-2">
                <div>
                  <p className="text-2xl font-bold text-purple-700">
                    ${telemetryOverview?.cost_per_hour_cents ? (telemetryOverview.cost_per_hour_cents / 100).toFixed(2) : '0.00'}
                  </p>
                  <p className="text-xs text-gray-600">Last hour</p>
                </div>
                <div className="pt-2 border-t border-purple-200">
                  <p className="text-sm font-medium text-purple-600">
                    {telemetryOverview?.cost_per_hour_cents ? telemetryOverview.cost_per_hour_cents.toFixed(2) : '0.00'} ¢
                  </p>
                  <p className="text-xs text-gray-600">Per hour (actual)</p>
                </div>
              </div>
            </div>
          </div>
          
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-600">
              <strong>Note:</strong> Environmental metrics are estimated based on token usage and typical LLM energy consumption patterns. 
              Actual values may vary based on hardware efficiency and energy sources.
            </p>
          </div>
          
          {/* Token Usage Details */}
          <div className="mt-6 border-t pt-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Token Usage Details</h4>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="bg-gray-50 rounded p-3">
                <p className="text-xs text-gray-600">Total Tokens (24h)</p>
                <p className="text-lg font-semibold text-gray-900">
                  {telemetryOverview?.tokens_per_hour ? (telemetryOverview.tokens_per_hour * 24).toLocaleString() : '0'}
                </p>
              </div>
              <div className="bg-gray-50 rounded p-3">
                <p className="text-xs text-gray-600">Avg Tokens/Hour</p>
                <p className="text-lg font-semibold text-gray-900">
                  {telemetryOverview?.tokens_per_hour?.toLocaleString() || '0'}
                </p>
              </div>
              <div className="bg-gray-50 rounded p-3">
                <p className="text-xs text-gray-600">Model</p>
                <p className="text-lg font-semibold text-gray-900">
                  {health?.version?.includes('mock') ? 'Mock LLM' : 'llama4scout'}
                </p>
              </div>
            </div>
          </div>
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
                    service.healthy === true
                      ? 'border-green-200 bg-green-50 hover:border-green-300'
                      : service.available === true
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
                      status={service.healthy === true ? 'green' : service.available === true ? 'yellow' : 'red'}
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
      {hasRole('ADMIN') && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Main Processor</h3>
            
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Processor Status</dt>
                <dd className="mt-2">
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-lg font-semibold ${
                    runtimeStatus?.is_paused
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {runtimeStatus?.is_paused ? 'PAUSED' : 'RUNNING'}
                  </span>
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Cognitive State</dt>
                <dd className="mt-2 text-2xl font-semibold text-gray-900">
                  {runtimeStatus?.cognitive_state || 'WORK'}
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Queue Depth</dt>
                <dd className="mt-2 text-2xl font-semibold text-gray-900">
                  {runtimeStatus?.queue_depth || 0}
                </dd>
              </div>
              
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg border-2 border-gray-200">
                <dt className="text-sm font-medium text-gray-500">Actions</dt>
                <dd className="mt-2">
                  {runtimeStatus?.is_paused ? (
                    <button
                      onClick={() => setConfirmDialog({ type: 'resumeRuntime' })}
                      className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700"
                    >
                      Resume
                    </button>
                  ) : (
                    <button
                      onClick={() => setConfirmDialog({ type: 'pauseRuntime' })}
                      className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-yellow-600 hover:bg-yellow-700"
                    >
                      Pause
                    </button>
                  )}
                </dd>
              </div>
            </div>
            
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-800">
                <strong>Note:</strong> The CIRIS system has one main processor that cycles through cognitive states (WAKEUP, WORK, PLAY, DREAM, SOLITUDE, SHUTDOWN). 
                Pausing affects the entire processor, not individual states.
              </p>
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
                    if (e.target.value === 'discord') {
                      setAdapterConfigModal({ type: e.target.value });
                      setAdapterConfig({
                        bot_token: '',
                        server_id: '',
                        monitored_channel_ids: [],
                        home_channel_id: '',
                        deferral_channel_id: '',
                        respond_to_mentions: true,
                        respond_to_dms: true,
                      });
                    } else {
                      setConfirmDialog({ type: 'registerAdapter', name: e.target.value });
                    }
                    e.target.value = '';
                  }
                }}
                className="block w-full max-w-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="">Select adapter type...</option>
                <option value="api">API</option>
                <option value="cli">CLI</option>
                <option value="discord">Discord</option>
              </select>
              <p className="text-sm text-gray-500">
                Select an adapter type to register a new instance
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Active Channels */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Active Communication Channels</h3>
          
          {channels && channels.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {channels.map((channel: any) => (
                <div
                  key={channel.channel_id}
                  className="relative p-4 rounded-lg border-2 border-gray-200 bg-gray-50 hover:shadow-md transition-all duration-200"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-gray-900">
                        {channel.display_name}
                      </h4>
                      <p className="text-xs text-gray-500 mt-1">
                        ID: {channel.channel_id}
                      </p>
                      <p className="text-xs text-gray-500">
                        Type: {channel.channel_type}
                      </p>
                    </div>
                    <StatusDot
                      status={channel.is_active ? 'green' : 'gray'}
                      className="flex-shrink-0 ml-2"
                    />
                  </div>
                  <div className="mt-3 space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-600">Messages:</span>
                      <span className="font-medium">{channel.message_count || 0}</span>
                    </div>
                    {channel.last_activity && (
                      <div className="flex justify-between text-xs">
                        <span className="text-gray-600">Last Activity:</span>
                        <span className="font-medium">
                          {new Date(channel.last_activity).toLocaleTimeString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500">No active channels found</p>
            </div>
          )}
        </div>
      </div>

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
                          adapter.adapter_type === 'api' && health?.status === 'healthy'
                            ? 'bg-green-100 text-green-800'
                            : adapter.is_running
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {adapter.adapter_type === 'api' && health?.status === 'healthy' ? 'Active' : adapter.is_running ? 'Active' : 'Loaded'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                        <div className="flex flex-col">
                          <span className="font-medium">
                            {channels?.filter((ch: any) => ch.channel_type === adapter.adapter_type).length || 0} active
                          </span>
                          <div className="text-xs text-gray-400 mt-1">
                            {channels
                              ?.filter((ch: any) => ch.channel_type === adapter.adapter_type)
                              ?.map((ch: any) => ch.display_name)
                              ?.join(', ') || 'No active channels'}
                          </div>
                        </div>
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
                  <ExclamationTriangleIcon className="text-yellow-600" size="sm" />
                </div>
                <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Confirm Action
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      {confirmDialog.type === 'pauseRuntime' && 'Are you sure you want to pause the runtime? This will temporarily stop all message processing.'}
                      {confirmDialog.type === 'resumeRuntime' && 'Are you sure you want to resume the runtime? Message processing will continue.'}
                      {confirmDialog.type === 'reloadAdapter' && `Are you sure you want to reload the ${confirmDialog.name} adapter?`}
                      {confirmDialog.type === 'unregisterAdapter' && `Are you sure you want to remove the ${confirmDialog.name} adapter? This cannot be undone.`}
                      {confirmDialog.type === 'registerAdapter' && `Are you sure you want to register a new ${confirmDialog.name} adapter?`}
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

      {/* Adapter Configuration Modal */}
      {adapterConfigModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true"></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div>
                <div className="text-center">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Configure Discord Adapter
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Enter the configuration details for the Discord adapter.
                    </p>
                  </div>
                </div>
                <div className="mt-5 space-y-4">
                  {/* Bot Token */}
                  <div>
                    <label htmlFor="bot_token" className="block text-sm font-medium text-gray-700">
                      Bot Token <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      id="bot_token"
                      value={adapterConfig.bot_token || ''}
                      onChange={(e) => setAdapterConfig({ ...adapterConfig, bot_token: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      placeholder="Your Discord bot token"
                    />
                  </div>

                  {/* Server ID */}
                  <div>
                    <label htmlFor="server_id" className="block text-sm font-medium text-gray-700">
                      Server ID (Guild ID) <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="server_id"
                      value={adapterConfig.server_id || ''}
                      onChange={(e) => setAdapterConfig({ ...adapterConfig, server_id: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      placeholder="Discord server/guild ID"
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      Right-click your server name in Discord and select "Copy Server ID" (requires Developer Mode)
                    </p>
                  </div>

                  {/* Home Channel ID */}
                  <div>
                    <label htmlFor="home_channel_id" className="block text-sm font-medium text-gray-700">
                      Home Channel ID
                    </label>
                    <input
                      type="text"
                      id="home_channel_id"
                      value={adapterConfig.home_channel_id || ''}
                      onChange={(e) => setAdapterConfig({ ...adapterConfig, home_channel_id: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      placeholder="Primary channel for agent communication"
                    />
                  </div>

                  {/* Monitored Channel IDs */}
                  <div>
                    <label htmlFor="monitored_channels" className="block text-sm font-medium text-gray-700">
                      Monitored Channel IDs
                    </label>
                    <input
                      type="text"
                      id="monitored_channels"
                      value={adapterConfig.monitored_channel_ids?.join(', ') || ''}
                      onChange={(e) => setAdapterConfig({ 
                        ...adapterConfig, 
                        monitored_channel_ids: e.target.value.split(',').map(s => s.trim()).filter(s => s) 
                      })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      placeholder="Comma-separated list of channel IDs to monitor"
                    />
                  </div>

                  {/* Deferral Channel ID */}
                  <div>
                    <label htmlFor="deferral_channel_id" className="block text-sm font-medium text-gray-700">
                      Deferral Channel ID
                    </label>
                    <input
                      type="text"
                      id="deferral_channel_id"
                      value={adapterConfig.deferral_channel_id || ''}
                      onChange={(e) => setAdapterConfig({ ...adapterConfig, deferral_channel_id: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                      placeholder="Channel for deferrals and WA guidance"
                    />
                  </div>

                  {/* Options */}
                  <div className="space-y-2">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={adapterConfig.respond_to_mentions}
                        onChange={(e) => setAdapterConfig({ ...adapterConfig, respond_to_mentions: e.target.checked })}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">Respond to mentions</span>
                    </label>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={adapterConfig.respond_to_dms}
                        onChange={(e) => setAdapterConfig({ ...adapterConfig, respond_to_dms: e.target.checked })}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">Respond to direct messages</span>
                    </label>
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  onClick={() => {
                    if (!adapterConfig.bot_token) {
                      toast.error('Bot token is required');
                      return;
                    }
                    if (!adapterConfig.server_id) {
                      toast.error('Server ID is required');
                      return;
                    }
                    registerAdapterMutation.mutate({ 
                      adapterType: 'discord', 
                      config: adapterConfig 
                    });
                  }}
                  disabled={registerAdapterMutation.isPending}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:col-start-2 sm:text-sm disabled:opacity-50"
                >
                  {registerAdapterMutation.isPending ? 'Registering...' : 'Register Adapter'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAdapterConfigModal(null);
                    setAdapterConfig({});
                  }}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:col-start-1 sm:text-sm"
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