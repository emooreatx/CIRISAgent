// CIRIS TypeScript SDK
// 
// A TypeScript SDK for the CIRIS v1 API that mirrors the Python SDK functionality
// with automatic response unwrapping, rate limiting, and type safety.

export { CIRISClient, cirisClient } from './client';
export type { CIRISClientOptions } from './client';

// Export all types
export * from './types';

// Export exceptions
export * from './exceptions';

// Export utilities
export { AuthStore } from './auth-store';
export { RateLimiter } from './rate-limiter';

// Export resources for advanced usage
export { AuthResource } from './resources/auth';
export { AgentResource } from './resources/agent';
export { SystemResource } from './resources/system';
export { MemoryResource } from './resources/memory';