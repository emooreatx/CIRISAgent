// CIRIS TypeScript SDK - Auth Resource

import { BaseResource } from './base';
import { User, LoginResponse } from '../types';
import { AuthStore, AuthToken } from '../auth-store';
import { CIRISAuthError } from '../exceptions';

export class AuthResource extends BaseResource {
  /**
   * Login with username and password
   */
  async login(username: string, password: string): Promise<User> {
    try {
      // Call login endpoint
      const response = await this.transport.post<LoginResponse>(
        '/v1/auth/login',
        { username, password },
        { skipAuth: true }
      );

      // Save token
      const token: AuthToken = {
        access_token: response.access_token,
        token_type: response.token_type,
        expires_in: response.expires_in,
        user_id: response.user_id,
        role: response.role,
        created_at: Date.now()
      };
      AuthStore.saveToken(token);

      // Get user info
      const user = await this.getMe();
      AuthStore.saveUser(user);

      return user;
    } catch (error) {
      throw new CIRISAuthError(this.buildErrorMessage('login', (error as Error).message));
    }
  }

  /**
   * Logout current user
   */
  async logout(): Promise<void> {
    try {
      await this.transport.post('/v1/auth/logout');
    } catch {
      // Ignore logout errors
    } finally {
      AuthStore.clearToken();
    }
  }

  /**
   * Get current user info
   */
  async getMe(): Promise<User> {
    return this.transport.get<User>('/v1/auth/me');
  }

  /**
   * Check if authenticated
   */
  isAuthenticated(): boolean {
    return AuthStore.isAuthenticated();
  }

  /**
   * Get current user from store
   */
  getCurrentUser(): User | null {
    return AuthStore.getUser();
  }

  /**
   * Get access token
   */
  getAccessToken(): string | null {
    return AuthStore.getAccessToken();
  }
}