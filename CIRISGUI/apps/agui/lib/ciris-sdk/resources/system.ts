// CIRIS TypeScript SDK - System Resource

import { BaseResource } from './base';
import {
  HealthStatus,
  ServiceInfo,
  ResourceUsage
} from '../types';

export interface RuntimeControlResponse {
  status: string;
  message: string;
  timestamp: string;
}

export interface ProcessorInfo {
  name: string;
  state: string;
  is_paused: boolean;
  last_activity?: string;
}

export interface AdapterInfo {
  adapter_id: string;
  adapter_type: string;
  is_running: boolean;
  channels: string[];
  message_count: number;
  error_count: number;
  created_at: string;
  last_activity?: string;
  config?: Record<string, any>;
}

export interface AdapterListResponse {
  adapters: AdapterInfo[];
  total_count: number;
  running_count: number;
}

export interface AdapterOperationResult {
  success: boolean;
  adapter_id?: string;
  message: string;
  adapter_type?: string;
}

export interface RegisterAdapterRequest {
  config?: Record<string, any>;
}

export class SystemResource extends BaseResource {
  /**
   * Get system health status
   */
  async getHealth(): Promise<HealthStatus> {
    return this.transport.get<HealthStatus>('/v1/system/health');
  }

  /**
   * Get all services status
   */
  async getServices(): Promise<{
    services: ServiceInfo[];
    total_services: number;
    healthy_services: number;
    timestamp: string;
  }> {
    return this.transport.get('/v1/system/services');
  }

  /**
   * Get resource usage
   */
  async getResources(): Promise<ResourceUsage> {
    return this.transport.get<ResourceUsage>('/v1/system/resources');
  }

  /**
   * Pause runtime processing
   */
  async pauseRuntime(): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>('/v1/system/runtime/pause');
  }

  /**
   * Resume runtime processing
   */
  async resumeRuntime(): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>('/v1/system/runtime/resume');
  }

  /**
   * Get runtime status
   */
  async getRuntimeStatus(): Promise<{
    is_paused: boolean;
    pause_reason?: string;
    paused_at?: string;
    paused_by?: string;
  }> {
    return this.transport.get('/v1/system/runtime/status');
  }

  /**
   * Get runtime state
   */
  async getRuntimeState(): Promise<{
    success: boolean;
    message: string;
    processor_state: string;
    cognitive_state: string;
    queue_depth: number;
  }> {
    return this.transport.post('/v1/system/runtime/state', {});
  }

  /**
   * Get all processors
   */
  async getProcessors(): Promise<ProcessorInfo[]> {
    return this.transport.get<ProcessorInfo[]>('/v1/system/processors');
  }

  /**
   * Pause a specific processor
   */
  async pauseProcessor(processorName: string, duration?: number): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>(
      `/v1/system/processors/${processorName}/pause`,
      { duration }
    );
  }

  /**
   * Resume a specific processor
   */
  async resumeProcessor(processorName: string): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>(
      `/v1/system/processors/${processorName}/resume`
    );
  }

  /**
   * Get all adapters
   */
  async getAdapters(): Promise<AdapterListResponse> {
    return this.transport.get<AdapterListResponse>('/v1/system/adapters');
  }

  /**
   * Get a specific adapter
   */
  async getAdapter(adapterId: string): Promise<AdapterInfo> {
    return this.transport.get<AdapterInfo>(`/v1/system/adapters/${adapterId}`);
  }

  /**
   * Register a new adapter
   */
  async registerAdapter(
    adapterType: string,
    config?: Record<string, any>
  ): Promise<AdapterOperationResult> {
    return this.transport.post<AdapterOperationResult>(
      `/v1/system/adapters/${adapterType}`,
      { config }
    );
  }

  /**
   * Unregister an adapter
   */
  async unregisterAdapter(adapterId: string): Promise<AdapterOperationResult> {
    return this.transport.delete<AdapterOperationResult>(
      `/v1/system/adapters/${adapterId}`
    );
  }

  /**
   * Reload an adapter
   */
  async reloadAdapter(adapterId: string): Promise<AdapterOperationResult> {
    return this.transport.put<AdapterOperationResult>(
      `/v1/system/adapters/${adapterId}/reload`
    );
  }

  /**
   * Restart a service
   */
  async restartService(serviceName: string): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>(
      `/v1/system/services/${serviceName}/restart`
    );
  }

  /**
   * Pause an adapter
   */
  async pauseAdapter(adapterName: string, duration?: number): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>(
      `/v1/system/adapters/${adapterName}/pause`,
      { duration }
    );
  }

  /**
   * Resume an adapter
   */
  async resumeAdapter(adapterName: string): Promise<RuntimeControlResponse> {
    return this.transport.post<RuntimeControlResponse>(
      `/v1/system/adapters/${adapterName}/resume`
    );
  }
}