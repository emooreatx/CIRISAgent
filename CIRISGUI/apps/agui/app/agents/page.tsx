'use client';

import { useAgentDiscovery } from '@/hooks/useAgentDiscovery';
import { AgentSelector } from '@/components/agent-selector';
import { useState } from 'react';
import { AlertCircle, CheckCircle, Clock, Server, RefreshCw, Activity } from 'lucide-react';
import { DeploymentStatus } from '@/lib/ciris-sdk/resources/manager';

export default function AgentsPage() {
  const {
    agents,
    loading,
    error,
    selectedAgent,
    getDeploymentStatus,
    notifyUpdate,
    fetchAgents
  } = useAgentDiscovery({ refreshInterval: 30000 });

  const [deploymentStatus, setDeploymentStatus] = useState<DeploymentStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [notifying, setNotifying] = useState(false);

  const handleAgentSelect = async (agentId: string) => {
    setLoadingStatus(true);
    setDeploymentStatus(null);
    
    try {
      const status = await getDeploymentStatus(agentId);
      setDeploymentStatus(status);
    } catch (err) {
      console.error('Failed to get deployment status:', err);
    } finally {
      setLoadingStatus(false);
    }
  };

  const handleNotifyUpdate = async () => {
    if (!selectedAgent) return;
    
    setNotifying(true);
    try {
      await notifyUpdate(
        selectedAgent.agent_id,
        'v1.2.0',
        'Bug fixes and performance improvements',
        'normal'
      );
      alert('Update notification sent to agent');
    } catch (err) {
      alert('Failed to send update notification');
    } finally {
      setNotifying(false);
    }
  };

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Agent Management</h1>
          <p className="text-gray-600 mt-2">
            Discover and manage CIRIS agents through CIRISManager
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Agent Selector */}
          <div>
            <AgentSelector 
              onAgentSelect={handleAgentSelect}
              className="h-full"
            />
          </div>

          {/* Agent Details */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
              <Activity className="w-5 h-5 mr-2" />
              Agent Details
            </h2>

            {selectedAgent ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-medium">{selectedAgent.agent_name}</h3>
                  <p className="text-sm text-gray-600">{selectedAgent.agent_id}</p>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Status:</span>
                    <p className="font-medium">{selectedAgent.status}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Health:</span>
                    <p className="font-medium">{selectedAgent.health || 'Unknown'}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Container:</span>
                    <p className="font-medium">{selectedAgent.container_name}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">API Endpoint:</span>
                    <p className="font-medium">{selectedAgent.api_endpoint || 'Not exposed'}</p>
                  </div>
                </div>

                {selectedAgent.update_available && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <div className="flex items-start">
                      <AlertCircle className="w-5 h-5 text-yellow-600 mr-2 mt-0.5" />
                      <div className="flex-1">
                        <p className="text-yellow-800 font-medium">Update Available</p>
                        <p className="text-yellow-700 text-sm mt-1">
                          A new version is available for this agent.
                        </p>
                        <button
                          onClick={handleNotifyUpdate}
                          disabled={notifying}
                          className="mt-2 px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700 disabled:opacity-50"
                        >
                          {notifying ? 'Notifying...' : 'Notify Agent'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Deployment Status */}
                {loadingStatus ? (
                  <div className="text-center py-4">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
                    <p className="text-sm text-gray-500 mt-2">Loading deployment status...</p>
                  </div>
                ) : deploymentStatus ? (
                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-2">Deployment Status</h4>
                    <div className="bg-gray-50 rounded-lg p-3 text-sm">
                      <p className="font-medium">{deploymentStatus.status}</p>
                      <p className="text-gray-600 mt-1">{deploymentStatus.message}</p>
                      {deploymentStatus.staged_container && (
                        <p className="text-gray-500 mt-2">
                          Staged: {deploymentStatus.staged_container}
                        </p>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Server className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                <p>Select an agent to view details</p>
              </div>
            )}
          </div>
        </div>

        {/* Manager Health Status */}
        <div className="mt-6 bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <CheckCircle className="w-5 h-5 text-green-500 mr-2" />
              <span className="text-sm text-gray-700">
                CIRISManager connected • {agents.length} agents discovered
              </span>
            </div>
            <button
              onClick={fetchAgents}
              disabled={loading}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}