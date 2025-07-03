// CIRIS TypeScript SDK - Main Client

import { Transport, TransportOptions } from './transport';
import { AuthResource } from './resources/auth';
import { AgentResource } from './resources/agent';
import { SystemResource } from './resources/system';
import { MemoryResource } from './resources/memory';
import { AuditResource } from './resources/audit';
import { ConfigResource } from './resources/config';
import { TelemetryResource } from './resources/telemetry';
import { WiseAuthorityResource } from './resources/wise-authority';
import { EmergencyResource } from './resources/emergency';
import { User } from './types';

export interface CIRISClientOptions {
  baseURL?: string;
  timeout?: number;
  maxRetries?: number;
  enableRateLimiting?: boolean;
  onAuthError?: () => void;
}

export class CIRISClient {
  private transport: Transport;
  
  // Resource instances
  public readonly auth: AuthResource;
  public readonly agent: AgentResource;
  public readonly system: SystemResource;
  public readonly memory: MemoryResource;
  public readonly audit: AuditResource;
  public readonly config: ConfigResource;
  public readonly telemetry: TelemetryResource;
  public readonly wiseAuthority: WiseAuthorityResource;
  public readonly emergency: EmergencyResource;

  constructor(options: CIRISClientOptions = {}) {
    const transportOptions: TransportOptions = {
      baseURL: options.baseURL || 'http://localhost:8080',
      timeout: options.timeout,
      maxRetries: options.maxRetries,
      enableRateLimiting: options.enableRateLimiting !== false, // Default true
      onAuthError: options.onAuthError || (() => {
        // Default behavior: redirect to login
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      })
    };

    this.transport = new Transport(transportOptions);
    
    // Initialize resources
    this.auth = new AuthResource(this.transport);
    this.agent = new AgentResource(this.transport);
    this.system = new SystemResource(this.transport);
    this.memory = new MemoryResource(this.transport);
    this.audit = new AuditResource(this.transport);
    this.config = new ConfigResource(this.transport);
    this.telemetry = new TelemetryResource(this.transport);
    this.wiseAuthority = new WiseAuthorityResource(this.transport);
    this.emergency = new EmergencyResource(this.transport);
  }

  /**
   * Login convenience method
   */
  async login(username: string, password: string): Promise<User> {
    return this.auth.login(username, password);
  }

  /**
   * Logout convenience method
   */
  async logout(): Promise<void> {
    return this.auth.logout();
  }

  /**
   * Check if authenticated
   */
  isAuthenticated(): boolean {
    return this.auth.isAuthenticated();
  }

  /**
   * Get current user
   */
  getCurrentUser(): User | null {
    return this.auth.getCurrentUser();
  }

  /**
   * Send a message to the agent (convenience method)
   */
  async interact(message: string, options?: { channel_id?: string; context?: Record<string, any> }) {
    return this.agent.interact(message, options);
  }

  /**
   * Get agent status (convenience method)
   */
  async getStatus() {
    return this.agent.getStatus();
  }

  /**
   * Get system health (convenience method)
   */
  async getHealth() {
    return this.system.getHealth();
  }
}

// Export a singleton instance for easy use
export const cirisClient = new CIRISClient();

// Export everything for advanced usage
export * from './types';
export * from './exceptions';
export * from './auth-store';
export * from './rate-limiter';
export * from './transport';