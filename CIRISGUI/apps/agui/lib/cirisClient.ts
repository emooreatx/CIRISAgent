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

  // Processor control
  async singleStep(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/processor/step`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async pauseProcessing(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/processor/pause`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async resumeProcessing(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/processor/resume`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  async getProcessingQueue(): Promise<any> {
    const res = await fetch(`${this.baseUrl}/v1/system/processor/queue`);
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
}
