// CIRIS TypeScript SDK - Users Resource

import { BaseResource } from './base';
import { APIRole, WARole } from '../types';

export interface UserSummary {
  user_id: string;
  username: string;
  auth_type: 'password' | 'oauth' | 'api_key';
  api_role: APIRole;
  wa_role?: WARole;
  wa_id?: string;
  oauth_provider?: string;
  oauth_email?: string;
  created_at: string;
  last_login?: string;
  is_active: boolean;
}

export interface UserDetail extends UserSummary {
  permissions: string[];
  oauth_external_id?: string;
  wa_parent_id?: string;
  wa_auto_minted: boolean;
  api_keys_count: number;
}

export interface UserListParams {
  page?: number;
  page_size?: number;
  search?: string;
  auth_type?: string;
  api_role?: APIRole;
  wa_role?: WARole;
  is_active?: boolean;
}

export interface PaginatedUsers {
  items: UserSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UpdateUserRequest {
  api_role?: APIRole;
  is_active?: boolean;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  api_role?: APIRole;
}

export interface MintWARequest {
  wa_role: WARole;
  signature: string;
}

export interface UserAPIKey {
  key_id: string;
  key_prefix: string;
  created_at: string;
  last_used?: string;
  expires_at?: string;
  is_active: boolean;
}

export class UsersResource extends BaseResource {
  /**
   * List all users with optional filtering
   */
  async list(params?: UserListParams): Promise<PaginatedUsers> {
    return this.transport.get<PaginatedUsers>('/v1/users', { params });
  }

  /**
   * Get detailed information about a specific user
   */
  async get(userId: string): Promise<UserDetail> {
    return this.transport.get<UserDetail>(`/v1/users/${userId}`);
  }

  /**
   * Create a new user
   * Requires: users.create permission (SYSTEM_ADMIN only)
   */
  async create(data: CreateUserRequest): Promise<UserDetail> {
    return this.transport.post<UserDetail>('/v1/users', data);
  }

  /**
   * Update user information (role, active status)
   */
  async update(userId: string, data: UpdateUserRequest): Promise<UserDetail> {
    return this.transport.put<UserDetail>(`/v1/users/${userId}`, data);
  }

  /**
   * Change user password
   * Users can change their own password.
   * SYSTEM_ADMIN can change any password without knowing current.
   */
  async changePassword(userId: string, data: ChangePasswordRequest): Promise<{ message: string }> {
    return this.transport.put<{ message: string }>(`/v1/users/${userId}/password`, data);
  }

  /**
   * Mint a user as a Wise Authority
   * Requires: wa.mint permission (ROOT WA only)
   * Also requires valid Ed25519 signature from ROOT private key.
   */
  async mintWiseAuthority(userId: string, data: MintWARequest): Promise<UserDetail> {
    return this.transport.post<UserDetail>(`/v1/users/${userId}/mint-wa`, data);
  }

  /**
   * Deactivate a user account
   * Requires: users.delete permission (SYSTEM_ADMIN only)
   */
  async deactivate(userId: string): Promise<{ message: string }> {
    return this.transport.delete<{ message: string }>(`/v1/users/${userId}`);
  }

  /**
   * List API keys for a user
   * Users can view their own keys.
   * ADMIN+ can view any user's keys.
   */
  async listAPIKeys(userId: string): Promise<UserAPIKey[]> {
    return this.transport.get<UserAPIKey[]>(`/v1/users/${userId}/api-keys`);
  }
}