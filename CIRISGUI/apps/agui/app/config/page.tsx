'use client';

import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import toast from 'react-hot-toast';
import { SpinnerIcon, ExclamationTriangleIcon } from '../../components/Icons';


export default function ConfigPage() {
  const [editedConfig, setEditedConfig] = useState<any>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['root']));
  const [showDiff, setShowDiff] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch configuration
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => cirisClient.config.getConfig(),
  });

  // Update configuration mutation
  const updateConfigMutation = useMutation({
    mutationFn: async (updates: any) => {
      return cirisClient.config.updateConfig(updates);
    },
    onSuccess: () => {
      toast.success('Configuration updated successfully');
      queryClient.invalidateQueries({ queryKey: ['config'] });
      setEditedConfig(null);
      setShowDiff(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update configuration');
    },
  });


  // Handle field changes in form mode
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

  // Handle JSON editor changes
  const handleJsonChange = (jsonString: string) => {
    try {
      const parsed = JSON.parse(jsonString);
      setEditedConfig(parsed);
      setJsonError(null);
    } catch (error) {
      setJsonError(`Invalid JSON: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Toggle section expansion
  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });
  };

  // Filter config based on search term
  const filterConfig = (obj: any, term: string): any => {
    if (!term) return obj;
    
    const result: any = {};
    for (const [key, value] of Object.entries(obj)) {
      if (key.toLowerCase().includes(term.toLowerCase())) {
        result[key] = value;
      } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        const filtered = filterConfig(value, term);
        if (Object.keys(filtered).length > 0) {
          result[key] = filtered;
        }
      } else if (String(value).toLowerCase().includes(term.toLowerCase())) {
        result[key] = value;
      }
    }
    return result;
  };

  // Calculate differences between configs
  const calculateDiff = (original: any, edited: any): any => {
    const diff: any = { added: {}, modified: {}, removed: {} };
    
    // Find added and modified
    const findChanges = (orig: any, edit: any, path: string[] = []) => {
      for (const key in edit) {
        const currentPath = [...path, key];
        const pathString = currentPath.join('.');
        
        if (!(key in orig)) {
          diff.added[pathString] = edit[key];
        } else if (typeof edit[key] === 'object' && edit[key] !== null && !Array.isArray(edit[key])) {
          findChanges(orig[key], edit[key], currentPath);
        } else if (JSON.stringify(orig[key]) !== JSON.stringify(edit[key])) {
          diff.modified[pathString] = { old: orig[key], new: edit[key] };
        }
      }
    };
    
    // Find removed
    const findRemoved = (orig: any, edit: any, path: string[] = []) => {
      for (const key in orig) {
        const currentPath = [...path, key];
        const pathString = currentPath.join('.');
        
        if (!(key in edit)) {
          diff.removed[pathString] = orig[key];
        } else if (typeof orig[key] === 'object' && orig[key] !== null && !Array.isArray(orig[key])) {
          findRemoved(orig[key], edit[key], currentPath);
        }
      }
    };
    
    findChanges(original, edited);
    findRemoved(original, edited);
    
    return diff;
  };

  const handleSave = () => {
    if (!editedConfig) return;
    
    if (showRaw && jsonError) {
      toast.error('Please fix JSON errors before saving');
      return;
    }
    
    // Show diff first if not already showing
    if (!showDiff) {
      setShowDiff(true);
      return;
    }
    
    // Calculate the updates
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
    updateConfigMutation.mutate(updates);
  };

  // Determine if a key is sensitive
  const isSensitiveKey = (key: string): boolean => {
    const sensitivePatterns = [
      'password', 'secret', 'key', 'token', 'credential',
      'api_key', 'private', 'auth', 'certificate'
    ];
    return sensitivePatterns.some(pattern => 
      key.toLowerCase().includes(pattern)
    );
  };

  // Get filtered config based on search
  const filteredConfig = useMemo(() => {
    const dataToFilter = editedConfig || config || {};
    return searchTerm ? filterConfig(dataToFilter, searchTerm) : dataToFilter;
  }, [config, editedConfig, searchTerm]);

  // Get current diff
  const currentDiff = useMemo(() => {
    if (!editedConfig || !config) return null;
    return calculateDiff(config, editedConfig);
  }, [config, editedConfig]);

  const renderConfigSection = (data: any, path: string[] = [], depth: number = 0) => {
    if (!data || typeof data !== 'object') return null;

    return Object.entries(data).map(([key, value]) => {
      const currentPath = [...path, key];
      const fieldId = currentPath.join('.');
      const sectionId = `section-${fieldId}`;
      const isSensitive = isSensitiveKey(key);

      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        const hasChildren = Object.keys(value).length > 0;
        const isExpanded = expandedSections.has(sectionId);

        return (
          <div key={fieldId} className={`${depth > 0 ? 'ml-4' : ''} mb-4`}>
            <button
              onClick={() => toggleSection(sectionId)}
              className="flex items-center space-x-2 text-sm font-medium text-gray-700 hover:text-gray-900 mb-2"
            >
              <svg
                className={`h-4 w-4 transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span className={`capitalize ${isSensitive ? 'text-orange-600' : ''}`}>
                {key.replace(/_/g, ' ')}
                {hasChildren && <span className="text-gray-400 ml-1">({Object.keys(value).length})</span>}
              </span>
            </button>
            {isExpanded && (
              <div className="border-l-2 border-gray-200 pl-4">
                {renderConfigSection(value, currentPath, depth + 1)}
              </div>
            )}
          </div>
        );
      }

      const currentValue = editedConfig 
        ? currentPath.reduce((acc, p) => acc?.[p], editedConfig)
        : value;

      return (
        <div key={fieldId} className={`${depth > 0 ? 'ml-4' : ''} mb-3`}>
          <label 
            htmlFor={fieldId} 
            className={`block text-sm font-medium mb-1 ${
              isSensitive ? 'text-orange-600' : 'text-gray-700'
            }`}
          >
            {key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1)}
            {isSensitive && (
              <span className="ml-2 text-xs text-orange-500">(Sensitive)</span>
            )}
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
              type={isSensitive ? 'password' : 'text'}
              value={currentValue || ''}
              onChange={(e) => handleFieldChange(currentPath, e.target.value)}
              className={`mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm ${
                isSensitive ? 'font-mono' : ''
              }`}
            />
          )}
        </div>
      );
    });
  };

  return (
    <ProtectedRoute requiredRole="ADMIN">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Configuration Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage system configuration with version control and backup capabilities
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Configuration Panel */}
          <div className="lg:col-span-2">
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                {/* Toolbar */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 space-y-3 sm:space-y-0">
                  <div className="flex-1 w-full sm:max-w-xs">
                    <input
                      type="text"
                      placeholder="Search configuration..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                  </div>
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => setShowRaw(!showRaw)}
                      className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      {showRaw ? 'Form Editor' : 'JSON Editor'}
                    </button>
                    {editedConfig && (
                      <>
                        <button
                          onClick={() => {
                            setEditedConfig(null);
                            setShowDiff(false);
                          }}
                          className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleSave}
                          disabled={updateConfigMutation.isPending}
                          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                        >
                          {updateConfigMutation.isPending ? 'Saving...' : showDiff ? 'Confirm Save' : 'Review Changes'}
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Configuration Content */}
                {isLoading ? (
                  <div className="text-center py-8">
                    <div className="inline-flex items-center">
                      <SpinnerIcon className="mr-3 text-indigo-600" size="md" />
                      Loading configuration...
                    </div>
                  </div>
                ) : showRaw ? (
                  <div>
                    <div className="mb-2 text-sm text-gray-600">
                      Edit the JSON directly. Validation will be performed before saving.
                    </div>
                    <textarea
                      value={JSON.stringify(editedConfig || config, null, 2)}
                      onChange={(e) => handleJsonChange(e.target.value)}
                      className={`w-full h-96 p-4 font-mono text-sm bg-gray-50 rounded-lg border ${
                        jsonError ? 'border-red-300' : 'border-gray-300'
                      } focus:border-indigo-500 focus:ring-indigo-500`}
                    />
                    {jsonError && (
                      <p className="mt-2 text-sm text-red-600">{jsonError}</p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-6">
                    {Object.keys(filteredConfig).length === 0 ? (
                      <p className="text-gray-500 text-center py-8">
                        No configuration items match your search.
                      </p>
                    ) : (
                      renderConfigSection(filteredConfig)
                    )}
                  </div>
                )}

                {/* Diff Display */}
                {showDiff && currentDiff && editedConfig && (
                  <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                    <h4 className="text-sm font-medium text-gray-900 mb-3">Review Changes</h4>
                    <div className="space-y-2 text-sm">
                      {Object.keys(currentDiff.added).length > 0 && (
                        <div>
                          <h5 className="font-medium text-green-700">Added:</h5>
                          {Object.entries(currentDiff.added).map(([key, value]) => (
                            <div key={key} className="ml-4 text-green-600">
                              {key}: {JSON.stringify(value)}
                            </div>
                          ))}
                        </div>
                      )}
                      {Object.keys(currentDiff.modified).length > 0 && (
                        <div>
                          <h5 className="font-medium text-blue-700">Modified:</h5>
                          {Object.entries(currentDiff.modified).map(([key, change]: [string, any]) => (
                            <div key={key} className="ml-4">
                              <span className="text-gray-600">{key}:</span>
                              <span className="text-red-600 line-through ml-2">{JSON.stringify(change.old)}</span>
                              <span className="text-green-600 ml-2">→ {JSON.stringify(change.new)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {Object.keys(currentDiff.removed).length > 0 && (
                        <div>
                          <h5 className="font-medium text-red-700">Removed:</h5>
                          {Object.entries(currentDiff.removed).map(([key, value]) => (
                            <div key={key} className="ml-4 text-red-600">
                              {key}: {JSON.stringify(value)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Unsaved Changes Warning */}
                {editedConfig && !showDiff && (
                  <div className="mt-4 p-4 bg-yellow-50 rounded-md">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <ExclamationTriangleIcon className="text-yellow-400" size="md" />
                      </div>
                      <div className="ml-3">
                        <h3 className="text-sm font-medium text-yellow-800">
                          Unsaved Changes
                        </h3>
                        <div className="mt-2 text-sm text-yellow-700">
                          <p>You have unsaved configuration changes. Click "Review Changes" to see what will be modified.</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Tips Panel */}
          <div className="lg:col-span-1">
            <div className="bg-blue-50 rounded-lg p-4">
              <h4 className="text-sm font-medium text-blue-900 mb-2">Configuration Tips</h4>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• Sensitive fields are highlighted in orange</li>
                <li>• Use JSON editor for complex changes</li>
                <li>• Search works on both keys and values</li>
                <li>• Click section headers to expand/collapse</li>
              </ul>
            </div>
          </div>
        </div>

      </div>
    </ProtectedRoute>
  );
}