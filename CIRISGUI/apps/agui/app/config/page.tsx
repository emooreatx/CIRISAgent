"use client";

import React, { useState, useEffect } from "react";
import { CIRISClient } from "../../lib/cirisClient";

const client = new CIRISClient();

export default function ConfigurationManagementPage() {
  const [config, setConfig] = useState<any>(null);
  const [envVars, setEnvVars] = useState<any>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Configuration update state
  const [configPath, setConfigPath] = useState('');
  const [configValue, setConfigValue] = useState('');
  const [configScope, setConfigScope] = useState('runtime');
  const [configReason, setConfigReason] = useState('');
  const [configResult, setConfigResult] = useState<any>(null);

  // Configuration validation state
  const [validateData, setValidateData] = useState('{}');
  const [validatePath, setValidatePath] = useState('');
  const [validationResult, setValidationResult] = useState<any>(null);

  // Environment variable state
  const [envVarName, setEnvVarName] = useState('');
  const [envVarValue, setEnvVarValue] = useState('');
  const [envVarPersist, setEnvVarPersist] = useState(false);
  const [envResult, setEnvResult] = useState<any>(null);

  // Backup state
  const [backupName, setBackupName] = useState('');
  const [backupIncludeSensitive, setBackupIncludeSensitive] = useState(false);
  const [backupResult, setBackupResult] = useState<any>(null);

  // Restore state
  const [restoreBackupName, setRestoreBackupName] = useState('');
  const [restoreProfiles, setRestoreProfiles] = useState(true);
  const [restoreResult, setRestoreResult] = useState<any>(null);

  const fetchData = async () => {
    try {
      const [configResp, envResp, backupsResp] = await Promise.all([
        client.getRuntimeConfig().catch(e => ({ error: e.message })),
        client.listEnvironmentVars(false).catch(e => ({ error: e.message })),
        client.listConfigurationBackups().catch(e => [])
      ]);

      setConfig(configResp);
      setEnvVars(envResp);
      setBackups(backupsResp);
    } catch (error) {
      console.error('Failed to fetch configuration data:', error);
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

  // Configuration update handlers
  const handleUpdateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let value;
      try {
        value = JSON.parse(configValue);
      } catch {
        value = configValue; // Use as string if not valid JSON
      }

      const result = await client.updateRuntimeConfig(
        configPath,
        value,
        configScope,
        'strict',
        configReason || undefined
      );
      setConfigResult(result);
      await refresh();
    } catch (error) {
      setConfigResult({ error: error.message });
    }
  };

  const handleValidateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const data = JSON.parse(validateData);
      const result = await client.validateConfig(data, validatePath || undefined);
      setValidationResult(result);
    } catch (error) {
      setValidationResult({ error: error.message });
    }
  };

  const handleReloadConfig = async () => {
    try {
      const result = await client.reloadConfig();
      setConfigResult(result);
      await refresh();
    } catch (error) {
      setConfigResult({ error: error.message });
    }
  };

  // Environment variable handlers
  const handleSetEnvVar = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await client.setEnvironmentVar(envVarName, envVarValue, envVarPersist);
      setEnvResult(result);
      await refresh();
    } catch (error) {
      setEnvResult({ error: error.message });
    }
  };

  const handleDeleteEnvVar = async (varName: string) => {
    try {
      const result = await client.deleteEnvironmentVar(varName, false);
      setEnvResult(result);
      await refresh();
    } catch (error) {
      setEnvResult({ error: error.message });
    }
  };

  // Backup/restore handlers
  const handleCreateBackup = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await client.backupConfiguration(
        backupName || undefined,
        backupIncludeSensitive
      );
      setBackupResult(result);
      await refresh();
    } catch (error) {
      setBackupResult({ error: error.message });
    }
  };

  const handleRestoreBackup = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await client.restoreConfiguration(restoreBackupName, restoreProfiles);
      setRestoreResult(result);
      await refresh();
    } catch (error) {
      setRestoreResult({ error: error.message });
    }
  };

  if (loading) {
    return <div><h1>Configuration Management</h1><p>Loading...</p></div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1>Configuration Management</h1>
        <button onClick={refresh} disabled={refreshing}>
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Current Configuration */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Current Configuration</h2>
        {config && !config.error ? (
          <pre style={{ background: '#f8f8f8', padding: 15, borderRadius: 4, fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
            {JSON.stringify(config, null, 2)}
          </pre>
        ) : (
          <div style={{ padding: 10, background: '#fff3cd', borderRadius: 4 }}>
            Configuration unavailable: {config?.error || 'Unknown error'}
          </div>
        )}
      </section>

      {/* Configuration Update */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Update Configuration</h2>
        <form onSubmit={handleUpdateConfig} style={{ marginBottom: 15 }}>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Path:</label>
            <input
              type="text"
              value={configPath}
              onChange={e => setConfigPath(e.target.value)}
              placeholder="e.g., llm_services.openai.temperature"
              required
              style={{ width: 300 }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Value:</label>
            <input
              type="text"
              value={configValue}
              onChange={e => setConfigValue(e.target.value)}
              placeholder="Value (JSON or string)"
              required
              style={{ width: 300 }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Scope:</label>
            <select value={configScope} onChange={e => setConfigScope(e.target.value)}>
              <option value="runtime">Runtime (temporary)</option>
              <option value="session">Session (until restart)</option>
              <option value="persistent">Persistent (saved to file)</option>
            </select>
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Reason:</label>
            <input
              type="text"
              value={configReason}
              onChange={e => setConfigReason(e.target.value)}
              placeholder="Optional reason for change"
              style={{ width: 300 }}
            />
          </div>
          <button type="submit">Update Configuration</button>
          <button type="button" onClick={handleReloadConfig} style={{ marginLeft: 10 }}>
            Reload from Files
          </button>
        </form>

        {configResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12 }}>
            {JSON.stringify(configResult, null, 2)}
          </pre>
        )}
      </section>

      {/* Configuration Validation */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Validate Configuration</h2>
        <form onSubmit={handleValidateConfig} style={{ marginBottom: 15 }}>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Config Data:</label>
            <textarea
              rows={5}
              value={validateData}
              onChange={e => setValidateData(e.target.value)}
              placeholder='{"key": "value"}'
              style={{ width: 400 }}
            />
          </div>
          <div style={{ marginBottom: 10 }}>
            <label style={{ display: 'inline-block', width: 120 }}>Config Path:</label>
            <input
              type="text"
              value={validatePath}
              onChange={e => setValidatePath(e.target.value)}
              placeholder="Optional path to validate"
              style={{ width: 300 }}
            />
          </div>
          <button type="submit">Validate</button>
        </form>

        {validationResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12 }}>
            {JSON.stringify(validationResult, null, 2)}
          </pre>
        )}
      </section>

      {/* Environment Variables */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Environment Variables</h2>
        
        {/* Set Environment Variable */}
        <div style={{ marginBottom: 20 }}>
          <h3>Set Environment Variable</h3>
          <form onSubmit={handleSetEnvVar} style={{ marginBottom: 15 }}>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 120 }}>Name:</label>
              <input
                type="text"
                value={envVarName}
                onChange={e => setEnvVarName(e.target.value)}
                required
                style={{ width: 200 }}
              />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 120 }}>Value:</label>
              <input
                type="text"
                value={envVarValue}
                onChange={e => setEnvVarValue(e.target.value)}
                required
                style={{ width: 300 }}
              />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 120 }}>
                <input
                  type="checkbox"
                  checked={envVarPersist}
                  onChange={e => setEnvVarPersist(e.target.checked)}
                />
                Persist to .env file
              </label>
            </div>
            <button type="submit">Set Variable</button>
          </form>
        </div>

        {/* Current Environment Variables */}
        <div>
          <h3>Current Variables</h3>
          {envVars && !envVars.error ? (
            <div>
              <div style={{ marginBottom: 10 }}>
                <strong>Total Variables:</strong> {envVars.variables_count || 0} 
                (Sensitive: {envVars.sensitive_count || 0})
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f0f0f0' }}>
                      <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Name</th>
                      <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Value</th>
                      <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(envVars).filter(([key]) => !['variables_count', 'sensitive_count'].includes(key)).map(([name, value]) => (
                      <tr key={name}>
                        <td style={{ border: '1px solid #ddd', padding: 8 }}>{name}</td>
                        <td style={{ border: '1px solid #ddd', padding: 8, maxWidth: 300, wordBreak: 'break-all' }}>
                          {String(value)}
                        </td>
                        <td style={{ border: '1px solid #ddd', padding: 8 }}>
                          <button 
                            onClick={() => handleDeleteEnvVar(name)}
                            style={{ fontSize: 12, padding: '4px 8px' }}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ padding: 10, background: '#fff3cd', borderRadius: 4 }}>
              Environment variables unavailable: {envVars?.error || 'Unknown error'}
            </div>
          )}
        </div>

        {envResult && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12, marginTop: 15 }}>
            {JSON.stringify(envResult, null, 2)}
          </pre>
        )}
      </section>

      {/* Configuration Backup/Restore */}
      <section style={{ marginBottom: 30, padding: 15, border: '1px solid #ddd', borderRadius: 5 }}>
        <h2>Configuration Backup & Restore</h2>
        
        {/* Create Backup */}
        <div style={{ marginBottom: 25 }}>
          <h3>Create Backup</h3>
          <form onSubmit={handleCreateBackup} style={{ marginBottom: 15 }}>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 150 }}>Backup Name:</label>
              <input
                type="text"
                value={backupName}
                onChange={e => setBackupName(e.target.value)}
                placeholder="Optional backup name"
                style={{ width: 300 }}
              />
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 150 }}>
                <input
                  type="checkbox"
                  checked={backupIncludeSensitive}
                  onChange={e => setBackupIncludeSensitive(e.target.checked)}
                />
                Include sensitive data
              </label>
            </div>
            <button type="submit">Create Backup</button>
          </form>
        </div>

        {/* Restore Backup */}
        <div style={{ marginBottom: 25 }}>
          <h3>Restore Backup</h3>
          <form onSubmit={handleRestoreBackup} style={{ marginBottom: 15 }}>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 150 }}>Backup Name:</label>
              <select 
                value={restoreBackupName} 
                onChange={e => setRestoreBackupName(e.target.value)}
                required
                style={{ width: 300 }}
              >
                <option value="">Select backup to restore</option>
                {backups.map((backup, index) => (
                  <option key={index} value={backup.backup_name}>
                    {backup.backup_name} ({new Date(backup.created_time).toLocaleString()})
                  </option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'inline-block', width: 150 }}>
                <input
                  type="checkbox"
                  checked={restoreProfiles}
                  onChange={e => setRestoreProfiles(e.target.checked)}
                />
                Restore profiles
              </label>
            </div>
            <button type="submit" disabled={!restoreBackupName}>Restore Backup</button>
          </form>
        </div>

        {/* Available Backups */}
        <div>
          <h3>Available Backups ({backups.length})</h3>
          {backups.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#f0f0f0' }}>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Name</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Created</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Files</th>
                    <th style={{ border: '1px solid #ddd', padding: 8, textAlign: 'left' }}>Size</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.map((backup, index) => (
                    <tr key={index}>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>{backup.backup_name}</td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>
                        {new Date(backup.created_time).toLocaleString()}
                      </td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>{backup.files_count}</td>
                      <td style={{ border: '1px solid #ddd', padding: 8 }}>
                        {Math.round(backup.size_bytes / 1024)} KB
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No backups available</p>
          )}
        </div>

        {(backupResult || restoreResult) && (
          <pre style={{ background: '#f0f0f0', padding: 10, borderRadius: 4, fontSize: 12, marginTop: 15 }}>
            {JSON.stringify(backupResult || restoreResult, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}