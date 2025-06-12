"use client";

import React, { useState, useEffect } from "react";
import { CIRISClient } from "../../lib/cirisClient";

const client = new CIRISClient();

export default function SystemStatusPage() {
  const [telemetrySnapshot, setTelemetrySnapshot] = useState<any>(null);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [adapters, setAdapters] = useState<any[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [processorState, setProcessorState] = useState<any>(null);
  const [configuration, setConfiguration] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Metrics recording state
  const [metricName, setMetricName] = useState('');
  const [metricValue, setMetricValue] = useState<number>(0);
  const [metricTags, setMetricTags] = useState('{}');
  const [metricResult, setMetricResult] = useState<any>(null);

  // Metrics history state
  const [historyMetricName, setHistoryMetricName] = useState('');
  const [historyHours, setHistoryHours] = useState(24);
  const [metricsHistory, setMetricsHistory] = useState<any[]>([]);

  const fetchSystemData = async () => {
    try {
      setError(null);
      const [
        telemetryResp,
        healthResp,
        adaptersResp,
        servicesResp,
        processorResp,
        configResp
      ] = await Promise.all([
        client.getTelemetrySnapshot().catch(e => ({ error: e.message })),
        client.getSystemHealth().catch(e => ({ error: e.message })),
        client.getAdapters().catch(e => []),
        client.getServices().catch(e => []),
        client.getProcessorState().catch(e => ({ error: e.message })),
        client.getConfiguration().catch(e => ({ error: e.message }))
      ]);
      
      setTelemetrySnapshot(telemetryResp);
      setSystemHealth(healthResp);
      setAdapters(adaptersResp);
      setServices(servicesResp);
      setProcessorState(processorResp);
      setConfiguration(configResp);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchSystemData().finally(() => setLoading(false));
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    await fetchSystemData();
    setRefreshing(false);
  };

  const handleRecordMetric = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let tags = {};
      if (metricTags.trim()) {
        tags = JSON.parse(metricTags);
      }
      
      const result = await client.recordMetric(metricName, metricValue, tags);
      setMetricResult(result);
    } catch (error) {
      setMetricResult({ error: error.message });
    }
  };

  const handleGetMetricsHistory = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const history = await client.getMetricsHistory(historyMetricName, historyHours);
      setMetricsHistory(history);
    } catch (error) {
      setMetricsHistory([{ error: error.message }]);
    }
  };

  if (loading) {
    return <div><h1>System Status</h1><p>Loading system information...</p></div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1>System Status & Health</h1>
        <button onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ padding: 10, background: '#ffebee', border: '1px solid #f44336', borderRadius: 4, marginBottom: 20 }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* System Health Overview */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>System Health Overview</h2>
        {systemHealth && !systemHealth.error ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 15 }}>
            <div style={{ padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
              <strong>Overall Health:</strong>
              <div style={{ 
                color: systemHealth.overall_health === 'healthy' ? 'green' : 
                       systemHealth.overall_health === 'degraded' ? 'orange' : 'red',
                fontWeight: 'bold',
                textTransform: 'uppercase'
              }}>
                {systemHealth.overall_health}
              </div>
            </div>
            <div style={{ padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
              <strong>Processor:</strong>
              <div>{systemHealth.processor_status}</div>
            </div>
            <div style={{ padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
              <strong>Memory Usage:</strong>
              <div>{systemHealth.memory_usage_mb} MB</div>
            </div>
            <div style={{ padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
              <strong>Uptime:</strong>
              <div>{Math.round(systemHealth.uptime_seconds / 3600)} hours</div>
            </div>
            <div style={{ padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
              <strong>Healthy Adapters:</strong>
              <div>{systemHealth.adapters_healthy}</div>
            </div>
            <div style={{ padding: 10, background: '#f8f8f8', borderRadius: 4 }}>
              <strong>Healthy Services:</strong>
              <div>{systemHealth.services_healthy}</div>
            </div>
          </div>
        ) : (
          <div style={{ padding: 10, background: '#ffebee', borderRadius: 4 }}>
            System health information unavailable: {systemHealth?.error || 'Unknown error'}
          </div>
        )}
      </section>

      {/* Telemetry Snapshot */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Telemetry Snapshot</h2>
        {telemetrySnapshot && !telemetrySnapshot.error ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 15 }}>
              <div><strong>Timestamp:</strong> {new Date(telemetrySnapshot.timestamp).toLocaleString()}</div>
              <div><strong>Schema Version:</strong> {telemetrySnapshot.schema_version}</div>
              <div><strong>Runtime Uptime:</strong> {Math.round(telemetrySnapshot.runtime_uptime_seconds)}s</div>
              <div><strong>Memory Usage:</strong> {telemetrySnapshot.memory_usage_mb} MB</div>
              <div><strong>CPU Usage:</strong> {telemetrySnapshot.cpu_usage_percent}%</div>
              <div><strong>Overall Health:</strong> {telemetrySnapshot.overall_health}</div>
            </div>
          </div>
        ) : (
          <div style={{ padding: 10, background: '#fff3cd', borderRadius: 4 }}>
            Telemetry snapshot unavailable: {telemetrySnapshot?.error || 'Unknown error'}
          </div>
        )}
      </section>

      {/* Processor State */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Processor State</h2>
        {processorState && !processorState.error ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
            <div><strong>Running:</strong> {processorState.is_running ? 'Yes' : 'No'}</div>
            <div><strong>Current Round:</strong> {processorState.current_round}</div>
            <div><strong>Pending Thoughts:</strong> {processorState.thoughts_pending}</div>
            <div><strong>Processing Thoughts:</strong> {processorState.thoughts_processing}</div>
            <div><strong>Completed (24h):</strong> {processorState.thoughts_completed_24h}</div>
            <div><strong>Processor Mode:</strong> {processorState.processor_mode}</div>
            <div><strong>Idle Rounds:</strong> {processorState.idle_rounds}</div>
            <div><strong>Last Activity:</strong> {processorState.last_activity ? new Date(processorState.last_activity).toLocaleString() : 'Never'}</div>
          </div>
        ) : (
          <div style={{ padding: 10, background: '#fff3cd', borderRadius: 4 }}>
            Processor state unavailable: {processorState?.error || 'Unknown error'}
          </div>
        )}
      </section>

      {/* System Adapters */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>System Adapters ({adapters.length})</h2>
        {adapters.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f0f0f0' }}>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Name</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Type</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Status</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Capabilities</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Start Time</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {adapters.map((adapter, index) => (
                  <tr key={index}>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.name}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.type}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>
                      <span style={{ color: adapter.status === 'active' ? 'green' : 'red' }}>
                        {adapter.status}
                      </span>
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{adapter.capabilities?.join(', ') || 'None'}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>
                      {adapter.start_time ? new Date(adapter.start_time).toLocaleString() : 'N/A'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>
                      {adapter.last_activity ? new Date(adapter.last_activity).toLocaleString() : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No system adapters found</p>
        )}
      </section>

      {/* System Services */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>System Services ({services.length})</h2>
        {services.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f0f0f0' }}>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Name</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Type</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Handler</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Priority</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Status</th>
                  <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Circuit Breaker</th>
                </tr>
              </thead>
              <tbody>
                {services.map((service, index) => (
                  <tr key={index}>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{service.name}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{service.service_type}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{service.handler || 'Global'}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{service.priority}</td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>
                      <span style={{ color: service.status === 'healthy' ? 'green' : 'red' }}>
                        {service.status}
                      </span>
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: 8 }}>{service.circuit_breaker_state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No system services found</p>
        )}
      </section>

      {/* Metrics Recording */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Record Custom Metric</h2>
        <form onSubmit={handleRecordMetric} style={{ marginBottom: 15 }}>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Metric Name:</label>
            <input
              type="text"
              value={metricName}
              onChange={e => setMetricName(e.target.value)}
              required
              style={{ width: 200 }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Value:</label>
            <input
              type="number"
              step="any"
              value={metricValue}
              onChange={e => setMetricValue(parseFloat(e.target.value))}
              required
              style={{ width: 200 }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Tags (JSON):</label>
            <input
              type="text"
              value={metricTags}
              onChange={e => setMetricTags(e.target.value)}
              placeholder='{"key": "value"}'
              style={{ width: 300 }}
            />
          </div>
          <button type="submit">Record Metric</button>
        </form>

        {metricResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12 }}>
            {JSON.stringify(metricResult, null, 2)}
          </pre>
        )}
      </section>

      {/* Metrics History */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Metrics History</h2>
        <form onSubmit={handleGetMetricsHistory} style={{ marginBottom: 15 }}>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Metric Name:</label>
            <input
              type="text"
              value={historyMetricName}
              onChange={e => setHistoryMetricName(e.target.value)}
              required
              style={{ width: 200 }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Hours:</label>
            <input
              type="number"
              value={historyHours}
              onChange={e => setHistoryHours(parseInt(e.target.value))}
              min={1}
              max={168}
              style={{ width: 100 }}
            />
          </div>
          <button type="submit">Get History</button>
        </form>

        {metricsHistory.length > 0 && (
          <div>
            <h3>History Results ({metricsHistory.length} entries)</h3>
            <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
              {JSON.stringify(metricsHistory, null, 2)}
            </pre>
          </div>
        )}
      </section>

      {/* Configuration Snapshot */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Configuration Snapshot</h2>
        {configuration && !configuration.error ? (
          <pre style={{ background: '#f8f8f8', padding: 15, borderRadius: 4, fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
            {JSON.stringify(configuration, null, 2)}
          </pre>
        ) : (
          <div style={{ padding: 10, background: '#fff3cd', borderRadius: 4 }}>
            Configuration unavailable: {configuration?.error || 'Unknown error'}
          </div>
        )}
      </section>
    </div>
  );
}