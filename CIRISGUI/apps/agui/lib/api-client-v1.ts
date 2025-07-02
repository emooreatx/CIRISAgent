import axios, { AxiosInstance } from 'axios';
import Cookies from 'js-cookie';

// Types matching v1 API schemas
export interface User {
  user_id: string;
  username: string;
  role: 'OBSERVER' | 'ADMIN' | 'AUTHORITY' | 'SYSTEM_ADMIN';
  permissions: string[];
  created_at: string;
  last_login?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export interface InteractResponse {
  response: string;
  processing_time_ms: number;
  cognitive_state: string;
  timestamp: string;
}

export interface AgentStatus {
  name: string;
  agent_id: string;
  cognitive_state: string;
  is_paused: boolean;
  processor_status: any;
  current_thought?: any;
}

export interface AgentIdentity {
  name: string;
  agent_id: string;
  version: string;
  capabilities: string[];
  purpose: string;
  channel_context?: any;
}

export interface ConversationMessage {
  id: string;
  content: string;
  author: string;
  timestamp: string;
  is_agent: boolean;
}

export interface ConversationHistory {
  messages: ConversationMessage[];
  has_more: boolean;
  total_count: number;
}

export interface HealthStatus {
  status: string;
  uptime_seconds: number;
  memory_usage_mb: number;
  services: Record<string, any>;
  container_age_seconds?: number;
}

// API Client class for v1 endpoints
class APIClientV1 {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    // Force localhost for browser access
    const baseURL = typeof window !== 'undefined' 
      ? 'http://localhost:8080'  // Browser always uses localhost
      : (process.env.NEXT_PUBLIC_CIRIS_API_URL || 'http://localhost:8080');
      
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add auth token to requests
    this.client.interceptors.request.use((config) => {
      const token = this.token || Cookies.get('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Handle auth errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Clear auth and redirect to login
          this.token = null;
          Cookies.remove('auth_token');
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async login(username: string, password: string): Promise<User> {
    try {
      console.log('Login attempt with:', { username });
      
      const { data } = await this.client.post<LoginResponse>('/v1/auth/login', {
        username,
        password,
      });
      
      console.log('Login response:', data);
      
      // Store token
      this.token = data.access_token;
      Cookies.set('auth_token', data.access_token);
      
      // Get user info - add explicit auth header to ensure it's sent
      const userResponse = await this.client.get<User>('/v1/auth/me', {
        headers: {
          'Authorization': `Bearer ${data.access_token}`
        }
      });
      
      console.log('User response:', userResponse.data);
      
      // Create user object with username fallback
      const user = userResponse.data;
      if (!user.username && user.user_id) {
        user.username = user.user_id;
      }
      
      return user;
    } catch (error: any) {
      console.error('Login error:', error.response?.data || error.message);
      throw error;
    }
  }

  async logout(): Promise<void> {
    await this.client.post('/v1/auth/logout');
    this.token = null;
    Cookies.remove('auth_token');
  }

  async getCurrentUser(): Promise<User | null> {
    try {
      const { data } = await this.client.get<User>('/v1/auth/me');
      // API returns user directly, not wrapped in data
      return data;
    } catch (error) {
      return null;
    }
  }

  // Agent endpoints
  async interact(message: string, channel_id: string = 'web_ui'): Promise<InteractResponse> {
    const { data } = await this.client.post<InteractResponse>('/v1/agent/interact', {
      message,
      channel_id,
    });
    return data;
  }

  async getHistory(channel_id?: string, limit: number = 50): Promise<ConversationHistory> {
    const { data } = await this.client.get<any>('/v1/agent/history', {
      params: { channel_id, limit },
    });
    // API returns data wrapped in { data: { messages, total_count, has_more } }
    return data.data || data;
  }

  async getStatus(): Promise<AgentStatus> {
    const { data } = await this.client.get<AgentStatus>('/v1/agent/status');
    return data;
  }

  async getIdentity(): Promise<AgentIdentity> {
    const { data } = await this.client.get<AgentIdentity>('/v1/agent/identity');
    return data;
  }

  async getChannels(): Promise<string[]> {
    const { data } = await this.client.get<string[]>('/v1/agent/channels');
    return data;
  }

  // Memory endpoints
  async queryMemory(query: string, limit: number = 20): Promise<any[]> {
    const { data } = await this.client.get('/v1/memory/search', {
      params: { query, limit },
    });
    return data.nodes || [];
  }

  async getMemoryNode(nodeId: string): Promise<any> {
    const { data } = await this.client.get(`/v1/memory/node/${nodeId}`);
    return data;
  }

  async getMemoryStats(): Promise<any> {
    const { data } = await this.client.get('/v1/memory/stats');
    return data;
  }

  // System endpoints
  async getHealth(): Promise<HealthStatus> {
    const { data } = await this.client.get<HealthStatus>('/v1/system/health');
    return data;
  }

  async getServices(): Promise<any[]> {
    const { data } = await this.client.get('/v1/system/services');
    return data;
  }

  async getResources(): Promise<any> {
    const { data } = await this.client.get('/v1/system/resources');
    return data;
  }

  async pauseRuntime(): Promise<any> {
    const { data } = await this.client.post('/v1/system/runtime/pause');
    return data;
  }

  async resumeRuntime(): Promise<any> {
    const { data } = await this.client.post('/v1/system/runtime/resume');
    return data;
  }

  // Telemetry endpoints
  async getLogs(level?: string, service?: string, limit: number = 100): Promise<any[]> {
    const { data } = await this.client.get('/v1/telemetry/logs', {
      params: { level, service, limit },
    });
    return data.logs || [];
  }

  async getMetrics(metric_type?: string, start_time?: string, end_time?: string): Promise<any[]> {
    const { data } = await this.client.get('/v1/telemetry/metrics', {
      params: { metric_type, start_time, end_time },
    });
    return data.metrics || [];
  }

  async getIncidents(limit: number = 50): Promise<any[]> {
    const { data } = await this.client.get('/v1/telemetry/incidents', {
      params: { limit },
    });
    return data.incidents || [];
  }

  // Audit endpoints
  async getAuditTrail(
    start_time?: string,
    end_time?: string,
    service?: string,
    action?: string,
    limit: number = 100
  ): Promise<any[]> {
    const { data } = await this.client.get('/v1/audit/trail', {
      params: { start_time, end_time, service, action, limit },
    });
    return data.entries || [];
  }

  async exportAudit(start_time?: string, end_time?: string): Promise<any> {
    const { data } = await this.client.get('/v1/audit/export', {
      params: { start_time, end_time },
    });
    return data;
  }

  // Config endpoints (ADMIN only)
  async getConfig(): Promise<any> {
    const { data } = await this.client.get('/v1/config');
    return data;
  }

  async updateConfig(updates: Record<string, any>): Promise<any> {
    const { data } = await this.client.patch('/v1/config', updates);
    return data;
  }

  async backupConfig(): Promise<any> {
    const { data } = await this.client.post('/v1/config/backup');
    return data;
  }

  async restoreConfig(backup_id: string): Promise<any> {
    const { data } = await this.client.post('/v1/config/restore', { backup_id });
    return data;
  }

  // WA endpoints (AUTHORITY only)
  async getDeferrals(): Promise<any[]> {
    const { data } = await this.client.get('/v1/wa/deferrals');
    return data.deferrals || [];
  }

  async resolveDeferral(deferral_id: string, decision: string, reasoning: string): Promise<any> {
    const { data } = await this.client.post(`/v1/wa/resolve/${deferral_id}`, {
      decision,
      reasoning,
    });
    return data;
  }

  // Emergency endpoint (SYSTEM_ADMIN only)
  async emergencyShutdown(reason: string, signature: string): Promise<any> {
    const { data } = await this.client.post('/v1/emergency/shutdown', {
      reason,
      signature,
      initiator: 'web_ui',
    });
    return data;
  }

  // Runtime control endpoints
  async getProcessors(): Promise<any[]> {
    const { data } = await this.client.get('/v1/system/runtime/processors');
    return data.processors || [];
  }

  async pauseProcessor(processor_name: string, duration?: number): Promise<any> {
    const { data } = await this.client.post(`/v1/system/runtime/processors/${processor_name}/pause`, {
      duration,
    });
    return data;
  }

  async resumeProcessor(processor_name: string): Promise<any> {
    const { data } = await this.client.post(`/v1/system/runtime/processors/${processor_name}/resume`);
    return data;
  }

  async getAdapters(): Promise<any[]> {
    const { data } = await this.client.get('/v1/system/adapters');
    return data.adapters || [];
  }

  async pauseAdapter(adapter_name: string, duration?: number): Promise<any> {
    const { data } = await this.client.post(`/v1/system/adapters/${adapter_name}/pause`, {
      duration,
    });
    return data;
  }

  async resumeAdapter(adapter_name: string): Promise<any> {
    const { data } = await this.client.post(`/v1/system/adapters/${adapter_name}/resume`);
    return data;
  }

  // Profile endpoints
  async updateProfile(updates: { display_name?: string; preferences?: any }): Promise<any> {
    const { data } = await this.client.patch('/v1/profile', updates);
    return data;
  }

  async changePassword(current_password: string, new_password: string): Promise<any> {
    const { data } = await this.client.post('/v1/profile/change-password', {
      current_password,
      new_password,
    });
    return data;
  }

  // WebSocket connection
  connectWebSocket(): WebSocket {
    const baseUrl = process.env.NEXT_PUBLIC_CIRIS_API_URL || 'http://localhost:8080';
    const wsUrl = baseUrl.replace(/^http/, 'ws') + '/v1/ws';
    
    const ws = new WebSocket(wsUrl);
    
    // Add auth token to WebSocket
    ws.onopen = () => {
      const token = this.token || Cookies.get('auth_token');
      if (token) {
        ws.send(JSON.stringify({
          type: 'auth',
          token: token
        }));
      }
    };
    
    return ws;
  }
}

// Export singleton instance
export const apiClient = new APIClientV1();
export default apiClient;