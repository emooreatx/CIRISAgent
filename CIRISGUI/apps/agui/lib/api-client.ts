import axios, { AxiosInstance } from 'axios';
import Cookies from 'js-cookie';

// Types
export interface User {
  username: string;
  role: 'OBSERVER' | 'ADMIN' | 'AUTHORITY' | 'SYSTEM_ADMIN';
  permissions: string[];
  created_at: string;
}

export interface LoginResponse {
  user: User;
}

export interface InteractResponse {
  response: string;
  processing_time_ms: number;
  state: string;
  timestamp: string;
}

export interface AgentStatus {
  name: string;
  agent_id: string;
  cognitive_state: string;
  uptime_seconds: number;
  memory_usage_mb: number;
  is_paused: boolean;
}

export interface ConversationMessage {
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

// API Client class
class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081',
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,
    });

    // Add auth token to requests
    this.client.interceptors.request.use((config) => {
      const token = Cookies.get('auth_token');
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
          Cookies.remove('auth_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async login(username: string, password: string): Promise<User> {
    const { data } = await this.client.post<LoginResponse>('/api/auth/login', {
      username,
      password,
    });
    return data.user;
  }

  async logout(): Promise<void> {
    await this.client.post('/api/auth/logout');
    Cookies.remove('auth_token');
  }

  async getCurrentUser(): Promise<User | null> {
    const { data } = await this.client.get<{ user: User | null }>('/api/auth/me');
    return data.user;
  }

  // Agent endpoints
  async interact(message: string, context?: Record<string, any>): Promise<InteractResponse> {
    const { data } = await this.client.post<InteractResponse>('/api/agent/interact', {
      message,
      context,
    });
    return data;
  }

  async getHistory(limit: number = 50): Promise<ConversationHistory> {
    const { data } = await this.client.get<ConversationHistory>('/api/agent/history', {
      params: { limit },
    });
    return data;
  }

  async getStatus(): Promise<AgentStatus> {
    const { data } = await this.client.get<AgentStatus>('/api/agent/status');
    return data;
  }

  async getIdentity(): Promise<any> {
    const { data } = await this.client.get('/api/agent/identity');
    return data;
  }

  // Memory endpoints
  async queryMemory(query: string, limit: number = 20): Promise<any[]> {
    const { data } = await this.client.post('/api/memory/query', { query, limit });
    return data.nodes;
  }

  async getMemoryNode(nodeId: string): Promise<any> {
    const { data } = await this.client.get(`/api/memory/node/${nodeId}`);
    return data;
  }

  // System endpoints
  async getHealth(): Promise<any> {
    const { data } = await this.client.get('/api/system/health');
    return data;
  }

  async getServices(): Promise<any[]> {
    const { data } = await this.client.get('/api/system/services');
    return data.services;
  }

  async getResources(): Promise<any> {
    const { data } = await this.client.get('/api/system/resources');
    return data;
  }

  async pauseRuntime(): Promise<any> {
    const { data } = await this.client.post('/api/system/runtime/pause');
    return data;
  }

  async resumeRuntime(): Promise<any> {
    const { data } = await this.client.post('/api/system/runtime/resume');
    return data;
  }

  // Telemetry endpoints
  async getLogs(params?: { level?: string; service?: string; limit?: number }): Promise<any[]> {
    const { data } = await this.client.get('/api/telemetry/logs', { params });
    return data.logs;
  }

  async getMetrics(params?: {
    metric_type?: string;
    start_time?: string;
    end_time?: string;
  }): Promise<any[]> {
    const { data } = await this.client.get('/api/telemetry/metrics', { params });
    return data.metrics;
  }

  // Audit endpoints
  async getAuditTrail(params?: {
    action_type?: string;
    user_id?: string;
    limit?: number;
  }): Promise<any[]> {
    const { data } = await this.client.get('/api/audit/trail', { params });
    return data.entries;
  }

  // Config endpoints
  async getConfig(): Promise<any> {
    const { data } = await this.client.get('/api/config');
    return data;
  }

  async updateConfig(updates: Record<string, any>): Promise<any> {
    const { data } = await this.client.patch('/api/config', updates);
    return data;
  }

  // WA endpoints
  async getDeferrals(): Promise<any[]> {
    const { data } = await this.client.get('/api/wa/deferrals');
    return data.deferrals;
  }

  async resolveDeferral(
    deferralId: string,
    decision: string,
    reasoning: string
  ): Promise<any> {
    const { data } = await this.client.post(`/api/wa/resolve/${deferralId}`, {
      decision,
      reasoning,
    });
    return data;
  }

  // Tools endpoint
  async getTools(): Promise<any[]> {
    const { data } = await this.client.get('/api/tools');
    return data.tools || [];
  }

  // Emergency endpoint
  async emergencyShutdown(reason: string, signature: string): Promise<any> {
    const { data } = await this.client.post('/api/emergency/shutdown', {
      reason,
      signature,
    });
    return data;
  }

  // WebSocket connection
  connectWebSocket(): WebSocket {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8081/ws';
    return new WebSocket(wsUrl);
  }
}

// Export singleton instance
export const apiClient = new APIClient();