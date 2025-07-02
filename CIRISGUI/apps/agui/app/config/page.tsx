'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../lib/api-client';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import toast from 'react-hot-toast';

export default function ConfigPage() {
  const [editedConfig, setEditedConfig] = useState<any>(null);
  const [showRaw, setShowRaw] = useState(false);
  const queryClient = useQueryClient();

  // Fetch configuration
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => apiClient.getConfig(),
  });

  // Update configuration mutation
  const updateConfig = useMutation({
    mutationFn: (updates: any) => apiClient.updateConfig(updates),
    onSuccess: () => {
      toast.success('Configuration updated successfully');
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setEditedConfig(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update configuration');
    },
  });

  const handleFieldChange = (path: string[], value: any) => {
    const newConfig = { ...(editedConfig || config) };
    let current = newConfig;
    
    for (let i = 0; i < path.length - 1; i++) {
      if (!current[path[i]]) current[path[i]] = {};
      current = current[path[i]];
    }
    
    current[path[path.length - 1]] = value;
    setEditedConfig(newConfig);
  };

  const handleSave = () => {
    if (!editedConfig) return;
    
    // Calculate the diff between original and edited
    const updates: any = {};
    const findDifferences = (original: any, edited: any, path: string[] = []) => {
      for (const key in edited) {
        const currentPath = [...path, key];
        if (typeof edited[key] === 'object' && edited[key] !== null && !Array.isArray(edited[key])) {
          findDifferences(original[key] || {}, edited[key], currentPath);
        } else if (original[key] !== edited[key]) {
          let target = updates;
          for (let i = 0; i < currentPath.length - 1; i++) {
            if (!target[currentPath[i]]) target[currentPath[i]] = {};
            target = target[currentPath[i]];
          }
          target[currentPath[currentPath.length - 1]] = edited[key];
        }
      }
    };
    
    findDifferences(config, editedConfig);
    updateConfig.mutate(updates);
  };

  const renderConfigSection = (data: any, path: string[] = [], depth: number = 0) => {
    if (!data || typeof data !== 'object') return null;

    return Object.entries(data).map(([key, value]) => {
      const currentPath = [...path, key];
      const fieldId = currentPath.join('.');

      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        return (
          <div key={fieldId} className={`${depth > 0 ? 'ml-4' : ''} mb-4`}>
            <h4 className="text-sm font-medium text-gray-700 mb-2 capitalize">
              {key.replace(/_/g, ' ')}
            </h4>
            <div className="border-l-2 border-gray-200 pl-4">
              {renderConfigSection(value, currentPath, depth + 1)}
            </div>
          </div>
        );
      }

      const currentValue = editedConfig 
        ? currentPath.reduce((acc, p) => acc?.[p], editedConfig)
        : value;

      return (
        <div key={fieldId} className={`${depth > 0 ? 'ml-4' : ''} mb-3`}>
          <label htmlFor={fieldId} className="block text-sm font-medium text-gray-700 mb-1">
            {key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1)}
          </label>
          {typeof value === 'boolean' ? (
            <input
              id={fieldId}
              type="checkbox"
              checked={currentValue}
              onChange={(e) => handleFieldChange(currentPath, e.target.checked)}
              className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            />
          ) : typeof value === 'number' ? (
            <input
              id={fieldId}
              type="number"
              value={currentValue}
              onChange={(e) => handleFieldChange(currentPath, parseFloat(e.target.value) || 0)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          ) : Array.isArray(value) ? (
            <textarea
              id={fieldId}
              value={currentValue?.join('\n') || ''}
              onChange={(e) => handleFieldChange(currentPath, e.target.value.split('\n').filter(Boolean))}
              rows={3}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              placeholder="One value per line"
            />
          ) : (
            <input
              id={fieldId}
              type="text"
              value={currentValue || ''}
              onChange={(e) => handleFieldChange(currentPath, e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
          )}
        </div>
      );
    });
  };

  return (
    <ProtectedRoute requiredRole="ADMIN">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-medium text-gray-900">
                System Configuration
              </h3>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setShowRaw(!showRaw)}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  {showRaw ? 'Show Form' : 'Show Raw'}
                </button>
                {editedConfig && (
                  <>
                    <button
                      onClick={() => setEditedConfig(null)}
                      className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={updateConfig.isPending}
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      {updateConfig.isPending ? 'Saving...' : 'Save Changes'}
                    </button>
                  </>
                )}
              </div>
            </div>

            {isLoading ? (
              <div className="text-center py-4">Loading configuration...</div>
            ) : showRaw ? (
              <div className="bg-gray-50 rounded-lg p-4">
                <pre className="text-sm text-gray-800 whitespace-pre-wrap">
                  {JSON.stringify(editedConfig || config, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="space-y-6">
                {renderConfigSection(editedConfig || config)}
              </div>
            )}

            {editedConfig && (
              <div className="mt-4 p-4 bg-yellow-50 rounded-md">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-yellow-800">
                      Unsaved Changes
                    </h3>
                    <div className="mt-2 text-sm text-yellow-700">
                      <p>You have unsaved configuration changes. Click "Save Changes" to apply them.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}