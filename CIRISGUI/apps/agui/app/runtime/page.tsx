"use client";

import React, { useState, useEffect } from "react";
import { CIRISClient } from "../../lib/cirisClient";

const client = new CIRISClient();

export default function RuntimeControlPage() {
  const [runtimeStatus, setRuntimeStatus] = useState<any>(null);
  const [adapters, setAdapters] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [queueStatus, setQueueStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Adapter loading state
  const [newAdapterType, setNewAdapterType] = useState('discord');
  const [newAdapterId, setNewAdapterId] = useState('');
  const [newAdapterConfig, setNewAdapterConfig] = useState('{"bot_token": "", "channel_id": ""}');
  const [loadResult, setLoadResult] = useState<any>(null);

  // Processor control state
  const [processorResult, setProcessorResult] = useState<any>(null);

  // Profile loading state
  const [selectedProfile, setSelectedProfile] = useState('');
  const [profileResult, setProfileResult] = useState<any>(null);

  const fetchData = async () => {
    try {
      const [statusResp, adaptersResp, profilesResp, queueResp] = await Promise.all([
        client.getRuntimeStatus(),
        client.listAdapters(),
        client.listProfiles(),
        client.getProcessingQueue()
      ]);
      
      setRuntimeStatus(statusResp);
      setAdapters(adaptersResp);
      setProfiles(profilesResp);
      setQueueStatus(queueResp);
      
      if (profilesResp.length > 0 && !selectedProfile) {
        setSelectedProfile(profilesResp[0].name);
      }
    } catch (error) {
      console.error('Failed to fetch runtime data:', error);
    }
  };

  useEffect(() => {
    fetchData().finally(() => setLoading(false));
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  // Processor Control Actions
  const handleSingleStep = async () => {
    try {
      const result = await client.singleStep();
      setProcessorResult(result);
      await refresh();
    } catch (error) {
      setProcessorResult({ error: error.message });
    }
  };

  const handlePause = async () => {
    try {
      const result = await client.pauseProcessing();
      setProcessorResult(result);
      await refresh();
    } catch (error) {
      setProcessorResult({ error: error.message });
    }
  };

  const handleResume = async () => {
    try {
      const result = await client.resumeProcessing();
      setProcessorResult(result);
      await refresh();
    } catch (error) {
      setProcessorResult({ error: error.message });
    }
  };

  // Adapter Management Actions
  const handleLoadAdapter = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let config = {};
      if (newAdapterConfig.trim()) {
        config = JSON.parse(newAdapterConfig);
      }
      
      const result = await client.loadAdapter(
        newAdapterType,
        newAdapterId || undefined,
        config,
        true
      );
      setLoadResult(result);
      await refresh();
    } catch (error) {
      setLoadResult({ error: error.message });
    }
  };

  const handleUnloadAdapter = async (adapterId: string) => {
    try {
      const result = await client.unloadAdapter(adapterId, false);
      setLoadResult(result);
      await refresh();
    } catch (error) {
      setLoadResult({ error: error.message });
    }
  };

  // Profile Management Actions
  const handleLoadProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await client.loadProfile(selectedProfile);
      setProfileResult(result);
      await refresh();
    } catch (error) {
      setProfileResult({ error: error.message });
    }
  };

  if (loading) {
    return <div><h1>Runtime Control</h1><p>Loading...</p></div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1>Runtime Control</h1>
        <button onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Runtime Status Overview */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Runtime Status</h2>
        {runtimeStatus && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
            <div><strong>Processor:</strong> {runtimeStatus.processor_status}</div>
            <div><strong>Health:</strong> {runtimeStatus.health_status}</div>
            <div><strong>Profile:</strong> {runtimeStatus.current_profile}</div>
            <div><strong>Uptime:</strong> {Math.round(runtimeStatus.uptime_seconds)}s</div>
            <div><strong>Active Adapters:</strong> {runtimeStatus.active_adapters?.length || 0}</div>
            <div><strong>Loaded Adapters:</strong> {runtimeStatus.loaded_adapters?.length || 0}</div>
          </div>
        )}
      </section>

      {/* Processor Control */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Processor Control</h2>
        <div style={{ marginBottom: 15 }}>
          <button onClick={handleSingleStep} style={{ marginRight: 10 }}>Single Step</button>
          <button onClick={handlePause} style={{ marginRight: 10 }}>Pause</button>
          <button onClick={handleResume}>Resume</button>
        </div>
        
        {queueStatus && (
          <div style={{ marginBottom: 15, padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
            <strong>Queue Status:</strong> {queueStatus.queue_size || 0} items, 
            Processing: {queueStatus.processing ? 'Yes' : 'No'}
          </div>
        )}
        
        {processorResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12 }}>
            {JSON.stringify(processorResult, null, 2)}
          </pre>
        )}
      </section>

      {/* Adapter Management */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Adapter Management</h2>
        
        {/* Load New Adapter */}
        <div style={{ marginBottom: 20 }}>
          <h3>Load New Adapter</h3>
          <form onSubmit={handleLoadAdapter} style={{ marginBottom: 15 }}>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 100 }}>Type:</label>
              <select value={newAdapterType} onChange={e => setNewAdapterType(e.target.value)}>
                <option value="discord">Discord</option>
                <option value="api">API</option>
                <option value="cli">CLI</option>
              </select>
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 100 }}>ID:</label>
              <input
                type="text"
                value={newAdapterId}
                onChange={e => setNewAdapterId(e.target.value)}
                placeholder="Auto-generated if empty"
                style={{ width: 200 }}
              />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 100 }}>Config:</label>
              <textarea
                rows={3}
                style={{ width: 400 }}
                value={newAdapterConfig}
                onChange={e => setNewAdapterConfig(e.target.value)}
                placeholder="JSON configuration"
              />
            </div>
            <button type="submit">Load Adapter</button>
          </form>
        </div>

        {/* Current Adapters */}
        <div>
          <h3>Current Adapters ({adapters.length})</h3>
          {adapters.length === 0 ? (
            <p>No adapters loaded</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f0f0f0' }}>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>ID</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Type</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Status</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Health</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Services</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {adapters.map((adapter) => (
                    <tr key={adapter.adapter_id}>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.adapter_id}</td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.adapter}</td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>
                        <span style={{ 
                          color: adapter.is_running ? 'green' : 'red',
                          fontWeight: 'bold'
                        }}>
                          {adapter.is_running ? 'Running' : 'Stopped'}
                        </span>
                      </td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.health_status}</td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.services_count}</td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>
                        <button 
                          onClick={() => handleUnloadAdapter(adapter.adapter_id)}
                          style={{ fontSize: 12 }}
                        >
                          Unload
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {loadResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12, marginTop: 15 }}>
            {JSON.stringify(loadResult, null, 2)}
          </pre>
        )}
      </section>

      {/* Profile Management */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Profile Management</h2>
        
        <div style={{ marginBottom: 15 }}>
          <h3>Available Profiles ({profiles.length})</h3>
          {profiles.length === 0 ? (
            <p>No profiles available</p>
          ) : (
            <div>
              {profiles.map((profile) => (
                <div key={profile.name} style={{ 
                  padding: 10, 
                  marginBottom: 10, 
                  border: '1px solid #eee',
                  borderRadius: 4,
                  background: profile.is_active ? '#e8f5e8' : '#f8f8f8'
                }}>
                  <div style={{ fontWeight: 'bold' }}>
                    {profile.name} {profile.is_active && <span style={{ color: 'green' }}>(Active)</span>}
                  </div>
                  {profile.description && <div style={{ fontSize: 14, color: '#666' }}>{profile.description}</div>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <h3>Load Profile</h3>
          <form onSubmit={handleLoadProfile} style={{ marginBottom: 15 }}>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 100 }}>Profile:</label>
              <select value={selectedProfile} onChange={e => setSelectedProfile(e.target.value)}>
                {profiles.map(profile => (
                  <option key={profile.name} value={profile.name}>{profile.name}</option>
                ))}
              </select>
            </div>
            <button type="submit" disabled={!selectedProfile}>Load Profile</button>
          </form>
        </div>

        {profileResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12 }}>
            {JSON.stringify(profileResult, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}