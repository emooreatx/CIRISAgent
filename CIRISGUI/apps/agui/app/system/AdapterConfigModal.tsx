import React from 'react';
import toast from 'react-hot-toast';

interface AdapterConfigModalProps {
  adapterType: string;
  config: any;
  setConfig: (config: any) => void;
  onSubmit: (adapterType: string, config: any) => void;
  onClose: () => void;
  isPending?: boolean;
}

export function AdapterConfigModal({ 
  adapterType, 
  config, 
  setConfig, 
  onSubmit, 
  onClose,
  isPending = false 
}: AdapterConfigModalProps) {
  const handleSubmit = () => {
    // Validation based on adapter type
    if (adapterType === 'discord') {
      if (!config.bot_token) {
        toast.error('Bot token is required');
        return;
      }
      if (!config.server_id) {
        toast.error('Server ID is required');
        return;
      }
    } else if (adapterType === 'api') {
      if (!config.host) {
        toast.error('Host is required');
        return;
      }
      if (!config.port) {
        toast.error('Port is required');
        return;
      }
    }
    
    onSubmit(adapterType, config);
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    fontSize: '14px',
    marginTop: '5px'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '5px',
    fontSize: '14px',
    fontWeight: '500'
  };

  const fieldStyle = {
    marginBottom: '15px'
  };

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 9999 }}>
      <div style={{ 
        position: 'absolute', 
        top: '50%', 
        left: '50%', 
        transform: 'translate(-50%, -50%)', 
        backgroundColor: 'white', 
        padding: '30px', 
        borderRadius: '8px',
        maxWidth: '500px',
        width: '90%',
        maxHeight: '80vh',
        overflowY: 'auto'
      }}>
        <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '15px' }}>
          Configure {adapterType.charAt(0).toUpperCase() + adapterType.slice(1)} Adapter
        </h3>
        
        {/* Discord Configuration */}
        {adapterType === 'discord' && (
          <>
            <div style={fieldStyle}>
              <label style={labelStyle}>
                Bot Token <span style={{ color: 'red' }}>*</span>
              </label>
              <input
                type="password"
                value={config.bot_token || ''}
                onChange={(e) => setConfig({ ...config, bot_token: e.target.value })}
                style={inputStyle}
                placeholder="Your Discord bot token"
              />
            </div>
            
            <div style={fieldStyle}>
              <label style={labelStyle}>
                Server ID <span style={{ color: 'red' }}>*</span>
              </label>
              <input
                type="text"
                value={config.server_id || ''}
                onChange={(e) => setConfig({ ...config, server_id: e.target.value })}
                style={inputStyle}
                placeholder="Discord server/guild ID"
              />
            </div>
            
            <div style={fieldStyle}>
              <label style={labelStyle}>Home Channel ID</label>
              <input
                type="text"
                value={config.home_channel_id || ''}
                onChange={(e) => setConfig({ ...config, home_channel_id: e.target.value })}
                style={inputStyle}
                placeholder="Primary channel for agent"
              />
            </div>
          </>
        )}
        
        {/* API Configuration */}
        {adapterType === 'api' && (
          <>
            <div style={fieldStyle}>
              <label style={labelStyle}>
                Host <span style={{ color: 'red' }}>*</span>
              </label>
              <input
                type="text"
                value={config.host || ''}
                onChange={(e) => setConfig({ ...config, host: e.target.value })}
                style={inputStyle}
                placeholder="0.0.0.0"
              />
            </div>
            
            <div style={fieldStyle}>
              <label style={labelStyle}>
                Port <span style={{ color: 'red' }}>*</span>
              </label>
              <input
                type="number"
                value={config.port || ''}
                onChange={(e) => setConfig({ ...config, port: parseInt(e.target.value) || 8080 })}
                style={inputStyle}
                placeholder="8080"
              />
            </div>
            
            <div style={fieldStyle}>
              <label style={labelStyle}>CORS Origins</label>
              <input
                type="text"
                value={config.cors_origins?.join(', ') || '*'}
                onChange={(e) => setConfig({ ...config, cors_origins: e.target.value.split(',').map(s => s.trim()) })}
                style={inputStyle}
                placeholder="*, http://localhost:3000"
              />
            </div>
            
            <div style={fieldStyle}>
              <label>
                <input
                  type="checkbox"
                  checked={config.enable_auth || false}
                  onChange={(e) => setConfig({ ...config, enable_auth: e.target.checked })}
                  style={{ marginRight: '8px' }}
                />
                Enable Authentication
              </label>
            </div>
          </>
        )}
        
        {/* CLI Configuration */}
        {adapterType === 'cli' && (
          <>
            <div style={fieldStyle}>
              <label style={labelStyle}>Prompt</label>
              <input
                type="text"
                value={config.prompt || ''}
                onChange={(e) => setConfig({ ...config, prompt: e.target.value })}
                style={inputStyle}
                placeholder="> "
              />
            </div>
            
            <div style={fieldStyle}>
              <label style={labelStyle}>History File</label>
              <input
                type="text"
                value={config.history_file || ''}
                onChange={(e) => setConfig({ ...config, history_file: e.target.value })}
                style={inputStyle}
                placeholder=".ciris_history"
              />
            </div>
            
            <div style={fieldStyle}>
              <label>
                <input
                  type="checkbox"
                  checked={config.enable_colors || false}
                  onChange={(e) => setConfig({ ...config, enable_colors: e.target.checked })}
                  style={{ marginRight: '8px' }}
                />
                Enable Colors
              </label>
            </div>
          </>
        )}
        
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
          <button
            onClick={onClose}
            style={{ 
              padding: '8px 16px', 
              border: '1px solid #ccc', 
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isPending}
            style={{ 
              padding: '8px 16px', 
              backgroundColor: isPending ? '#ccc' : '#4f46e5', 
              color: 'white', 
              border: 'none',
              borderRadius: '4px',
              cursor: isPending ? 'not-allowed' : 'pointer'
            }}
          >
            {isPending ? 'Registering...' : 'Register Adapter'}
          </button>
        </div>
      </div>
    </div>
  );
}