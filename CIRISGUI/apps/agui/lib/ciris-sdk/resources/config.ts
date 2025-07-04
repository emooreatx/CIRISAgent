// CIRIS TypeScript SDK - Config Resource

import { BaseResource } from './base';
import { ConfigData } from '../types';

export interface ConfigValue {
  key: string;
  value: any;
  description?: string;
  updated_at: string;
  updated_by?: string;
}

export interface ConfigUpdateResponse {
  success: boolean;
  key: string;
  previous_value?: any;
  new_value: any;
  message?: string;
}

export interface ConfigDeleteResponse {
  success: boolean;
  key: string;
  message: string;
  deleted_value?: any;
}

export class ConfigResource extends BaseResource {
  /**
   * Get all configuration values
   */
  async getAll(): Promise<ConfigData> {
    return this.transport.get<ConfigData>('/v1/config');
  }

  /**
   * Update configuration values
   */
  async updateAll(config: ConfigData): Promise<{
    success: boolean;
    updated: string[];
    failed: string[];
    message: string;
  }> {
    return this.transport.post('/v1/config', config);
  }

  /**
   * Get a specific configuration value
   */
  async get(key: string): Promise<ConfigValue> {
    return this.transport.get<ConfigValue>(`/v1/config/${key}`);
  }

  /**
   * Set a specific configuration value
   */
  async set(key: string, value: any, description?: string): Promise<ConfigUpdateResponse> {
    return this.transport.put<ConfigUpdateResponse>(`/v1/config/${key}`, {
      value,
      description
    });
  }

  /**
   * Delete a specific configuration value
   */
  async delete(key: string): Promise<ConfigDeleteResponse> {
    return this.transport.delete<ConfigDeleteResponse>(`/v1/config/${key}`);
  }

  /**
   * Get configuration (alias for getAll)
   */
  async getConfig(): Promise<ConfigData> {
    return this.getAll();
  }

  /**
   * Update configuration (alias for updateAll)
   */
  async updateConfig(config: ConfigData): Promise<{
    success: boolean;
    updated: string[];
    failed: string[];
    message: string;
  }> {
    return this.updateAll(config);
  }

}