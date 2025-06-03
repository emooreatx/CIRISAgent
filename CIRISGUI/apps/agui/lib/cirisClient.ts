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
    return data.tools || [];
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
}
