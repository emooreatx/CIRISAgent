'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { cirisClient } from '../../lib/ciris-sdk';
import type { OAuthProvider } from '../../lib/ciris-sdk';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [oauthProviders, setOAuthProviders] = useState<OAuthProvider[]>([]);
  const { login } = useAuth();

  useEffect(() => {
    loadOAuthProviders();
  }, []);

  const loadOAuthProviders = async () => {
    try {
      const response = await cirisClient.auth.listOAuthProviders();
      setOAuthProviders(response.providers);
    } catch (error) {
      // OAuth providers not configured is ok
    }
  };

  const handleOAuthLogin = async (provider: string) => {
    try {
      const response = await cirisClient.auth.initiateOAuthLogin(provider, window.location.origin + '/oauth/callback');
      window.location.href = response.auth_url;
    } catch (error) {
      console.error('OAuth login error:', error);
    }
  };

  const getProviderIcon = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'google':
        return '🔵';
      case 'github':
        return '🐙';
      case 'discord':
        return '💬';
      default:
        return '🔑';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(username, password);
    } catch (error) {
      // Error is handled in AuthContext
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign in to CIRIS
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Use your credentials to access the CIRIS management interface
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <input type="hidden" name="remember" value="true" />
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="username" className="sr-only">
                Username
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
              />
            </div>
            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>

          <div className="text-sm text-center text-gray-600">
            <p>Default credentials:</p>
            <p className="font-mono">admin / ciris_admin_password</p>
          </div>

          {/* OAuth Login Options */}
          {oauthProviders.length > 0 && (
            <>
              <div className="mt-6">
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-300" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-gray-50 text-gray-500">Or continue with</span>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-3">
                  {oauthProviders.map((provider) => (
                    <button
                      key={provider.provider}
                      onClick={() => handleOAuthLogin(provider.provider)}
                      className="w-full inline-flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      <span className="mr-2 text-lg">{getProviderIcon(provider.provider)}</span>
                      Sign in with {provider.provider.charAt(0).toUpperCase() + provider.provider.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  );
}