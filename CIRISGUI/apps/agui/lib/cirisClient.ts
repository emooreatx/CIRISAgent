export class CIRISClient {
  constructor(private baseUrl: string = process.env.NEXT_PUBLIC_CIRIS_API_URL || '') {}

  async auditList(eventType?: string, limit: number = 100): Promise<any[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (eventType) params.append('event_type', eventType);
    const res = await fetch(`${this.baseUrl}/v1/audit?${params.toString()}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async logFetch(filename: string, tail: number = 100): Promise<string> {
    const res = await fetch(`${this.baseUrl}/v1/logs/${filename}?tail=${tail}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.text();
  }

  async memoryScopes(): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/v1/memory/scopes`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    return data.scopes || [];
  }

  async memoryStore(scope: string, key: string, value: any): Promise<void> {
    await fetch(`${this.baseUrl}/v1/memory/${encodeURIComponent(scope)}/store`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
  }

  async memoryEntries(scope: string): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/v1/memory/${encodeURIComponent(scope)}/entries`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    return data.entries || [];
  }

  async toolsList(): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/v1/tools`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    return data.map((tool: any) => tool.name) || [];
  }

  async toolExecute(name: string, args: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/tools/${name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(args),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async sendMessage(content: string, channelId: string = 'api'): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, channel_id: channelId }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getMessages(limit: number = 20): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/v1/messages?limit=${limit}`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    return data.messages || [];
  }

  async getStatus(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/status`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // System telemetry and control endpoints
  async getTelemetrySnapshot(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/telemetry`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getAdapters(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/v1/system/adapters`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getServices(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/v1/system/services`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getProcessorState(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/processor`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getConfiguration(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/configuration`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getSystemHealth(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/health`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Runtime Control - Processor Control
  async singleStep(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/processor/step`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async pauseProcessing(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/processor/pause`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async resumeProcessing(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/processor/resume`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async shutdownRuntime(reason?: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/processor/shutdown`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || 'GUI shutdown request' }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getProcessingQueue(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/processor/queue`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Runtime Control - Adapter Management
  async loadAdapter(adapterType: string, adapterId?: string, config: any = {}, autoStart: boolean = true): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/adapters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        adapter_type: adapterType, 
        adapter_id: adapterId, 
        config, 
        auto_start: autoStart 
      }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async unloadAdapter(adapterId: string, force: boolean = false): Promise<any> {
    const params = force ? '?force=true' : '';
    const res = await fetch(`${this.baseUrl}/v1/runtime/adapters/${adapterId}${params}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async listAdapters(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/adapters`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getAdapterInfo(adapterId: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/adapters/${adapterId}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Runtime Control - Configuration Management
  async getRuntimeConfig(path?: string, includeSensitive: boolean = false): Promise<any> {
    const params = new URLSearchParams();
    if (path) params.append('path', path);
    if (includeSensitive) params.append('include_sensitive', 'true');
    
    const res = await fetch(`${this.baseUrl}/v1/runtime/config?${params.toString()}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async updateRuntimeConfig(path: string, value: any, scope: string = 'runtime', validationLevel: string = 'strict', reason?: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, value, scope, validation_level: validationLevel, reason }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async validateConfig(configData: any, configPath?: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/config/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config_data: configData, config_path: configPath }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async reloadConfig(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/config/reload`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Runtime Control - Profile Management
  async listProfiles(): Promise<any[]> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/profiles`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async loadProfile(profileName: string, configPath?: string, scope: string = 'session'): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/profiles/${profileName}/load`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config_path: configPath, scope }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getProfile(profileName: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/profiles/${profileName}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Runtime Control - Status and Monitoring
  async getRuntimeStatus(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/status`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getRuntimeSnapshot(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/snapshot`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Missing Audit Operations
  async auditQuery(query: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/audit/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async auditLog(eventType: string, eventData: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/audit/log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: eventType, event_data: eventData }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Missing Memory Operations
  async memorySearch(query: string, scope?: string, limit: number = 10): Promise<any> {
    const payload: any = { query, limit };
    if (scope) payload.scope = scope;
    
    const res = await fetch(`${this.baseUrl}/v1/memory/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async memoryRecall(nodeId: string, scope?: string, nodeType?: string): Promise<any> {
    const payload: any = { node_id: nodeId };
    if (scope) payload.scope = scope;
    if (nodeType) payload.node_type = nodeType;
    
    const res = await fetch(`${this.baseUrl}/v1/memory/recall`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async memoryForget(scope: string, nodeId: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/memory/${scope}/${nodeId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async memoryTimeseries(scope?: string, hours: number = 24, correlationTypes?: string[]): Promise<any> {
    const params = new URLSearchParams({ hours: hours.toString() });
    if (scope) params.append('scope', scope);
    if (correlationTypes) params.append('correlation_types', correlationTypes.join(','));
    
    const res = await fetch(`${this.baseUrl}/v1/memory/timeseries?${params.toString()}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Missing Tool Operations  
  async toolValidate(toolName: string, parameters: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/tools/${toolName}/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parameters),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Missing Wise Authority Operations
  async requestGuidance(context: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/guidance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(context),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async submitDeferral(thoughtId: string, reason: string, context?: any): Promise<any> {
    const payload: any = { thought_id: thoughtId, reason };
    if (context) payload.context = context;
    
    const res = await fetch(`${this.baseUrl}/v1/defer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async listDeferrals(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/wa/deferrals`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getDeferralDetail(deferralId: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/wa/deferrals/${deferralId}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async submitFeedback(feedback: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/wa/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(feedback),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Missing Profile Management (CRUD)
  async createProfile(profileData: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/profiles`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async updateProfile(profileName: string, profileData: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/profiles/${profileName}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async deleteProfile(profileName: string): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/profiles/${profileName}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Missing Configuration Backup/Restore
  async backupConfiguration(description?: string, includeSensitive: boolean = false): Promise<any> {
    const payload: any = { include_profiles: true, include_env_vars: includeSensitive };
    if (description) payload.backup_name = description;
    
    const res = await fetch(`${this.baseUrl}/v1/runtime/config/backup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async restoreConfiguration(backupName: string, restoreProfiles: boolean = true): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/config/restore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        backup_name: backupName, 
        restore_profiles: restoreProfiles,
        restore_env_vars: false 
      }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async listConfigurationBackups(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/config/backups`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Metrics
  async recordMetric(metricName: string, value: number, tags?: Record<string, string>): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/metrics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metric_name: metricName, value, tags }),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getMetricsHistory(metricName: string, hours: number = 24): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/metrics/${metricName}?hours=${hours}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Service Registry Management Operations
  async listServices(handler?: string, serviceType?: string): Promise<any> {
    const params = new URLSearchParams();
    if (handler) params.append('handler', handler);
    if (serviceType) params.append('service_type', serviceType);
    const res = await fetch(`${this.baseUrl}/v1/runtime/services${params.toString() ? '?' + params.toString() : ''}`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getServiceHealth(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/services/health`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getServiceSelectionExplanation(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/runtime/services/selection-logic`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async resetCircuitBreakers(serviceType?: string): Promise<any> {
    const params = new URLSearchParams();
    if (serviceType) params.append('service_type', serviceType);
    const res = await fetch(`${this.baseUrl}/v1/runtime/services/circuit-breakers/reset${params.toString() ? '?' + params.toString() : ''}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async updateServicePriority(
    providerName: string, 
    priority?: string, 
    priorityGroup?: number, 
    strategy?: string
  ): Promise<any> {
    const data: any = {};
    if (priority) data.priority = priority;
    if (priorityGroup !== undefined) data.priority_group = priorityGroup;
    if (strategy) data.strategy = strategy;
    
    const res = await fetch(`${this.baseUrl}/v1/runtime/services/${providerName}/priority`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  // Convenience methods for service management
  async getLLMServices(): Promise<any[]> {
    const services = await this.listServices(undefined, 'llm');
    const llmServices: any[] = [];
    
    // Extract LLM services from both handlers and global services
    for (const [handler, serviceTypes] of Object.entries(services.handlers || {})) {
      if ((serviceTypes as any).llm) {
        for (const service of (serviceTypes as any).llm) {
          llmServices.push({
            scope: `handler:${handler}`,
            ...service
          });
        }
      }
    }
    
    for (const service of services.global_services?.llm || []) {
      llmServices.push({
        scope: 'global',
        ...service
      });
    }
    
    return llmServices;
  }

  async getCommunicationServices(): Promise<any[]> {
    const services = await this.listServices(undefined, 'communication');
    const commServices: any[] = [];
    
    // Extract communication services from both handlers and global services
    for (const [handler, serviceTypes] of Object.entries(services.handlers || {})) {
      if ((serviceTypes as any).communication) {
        for (const service of (serviceTypes as any).communication) {
          commServices.push({
            scope: `handler:${handler}`,
            ...service
          });
        }
      }
    }
    
    for (const service of services.global_services?.communication || []) {
      commServices.push({
        scope: 'global',
        ...service
      });
    }
    
    return commServices;
  }

  async getMemoryServices(): Promise<any[]> {
    const services = await this.listServices(undefined, 'memory');
    const memoryServices: any[] = [];
    
    // Extract memory services from both handlers and global services
    for (const [handler, serviceTypes] of Object.entries(services.handlers || {})) {
      if ((serviceTypes as any).memory) {
        for (const service of (serviceTypes as any).memory) {
          memoryServices.push({
            scope: `handler:${handler}`,
            ...service
          });
        }
      }
    }
    
    for (const service of services.global_services?.memory || []) {
      memoryServices.push({
        scope: 'global',
        ...service
      });
    }
    
    return memoryServices;
  }

  async diagnoseServiceIssues(): Promise<any> {
    const [health, services] = await Promise.all([
      this.getServiceHealth(),
      this.listServices()
    ]);
    
    const issues: string[] = [];
    const recommendations: string[] = [];
    
    // Check for unhealthy services
    if (health.unhealthy_services > 0) {
      issues.push(`${health.unhealthy_services} services are unhealthy`);
      recommendations.push('Check circuit breaker states and service logs');
    }
    
    // Check for missing critical services
    const requiredServices = ['llm', 'communication', 'memory', 'audit'];
    for (const serviceType of requiredServices) {
      let hasService = false;
      
      // Check global services
      if (services.global_services?.[serviceType]) {
        hasService = true;
      }
      
      // Check handler services
      for (const handlerServices of Object.values(services.handlers || {})) {
        if ((handlerServices as any)[serviceType]) {
          hasService = true;
          break;
        }
      }
      
      if (!hasService) {
        issues.push(`No ${serviceType} services registered`);
        recommendations.push(`Ensure adapters providing ${serviceType} services are loaded`);
      }
    }
    
    return {
      overall_health: health.overall_health || 'unknown',
      total_services: health.total_services || 0,
      healthy_services: health.healthy_services || 0,
      issues_found: issues.length,
      issues,
      recommendations,
      service_summary: {
        global_services: Object.keys(services.global_services || {}).length,
        handler_specific_services: Object.values(services.handlers || {}).reduce(
          (acc, serviceTypes) => acc + Object.keys(serviceTypes as any).length, 
          0
        )
      }
    };
  }
}
