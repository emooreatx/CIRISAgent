'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useQuery } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';

// Tool categories with descriptions and examples
const toolCategories = [
  {
    name: 'Communication Tools',
    icon: '💬',
    description: 'Tools for interacting with users across different channels',
    examples: [
      'speak - Send messages to users',
      'observe - Monitor channel activity',
      'broadcast - Send announcements'
    ],
    adapters: ['Discord', 'API', 'CLI']
  },
  {
    name: 'Memory Tools',
    icon: '🧠',
    description: 'Tools for storing and retrieving information',
    examples: [
      'memorize - Store new information',
      'recall - Retrieve stored information',
      'search - Find relevant memories',
      'forget - Remove outdated information'
    ],
    adapters: ['Memory Graph', 'Vector Store']
  },
  {
    name: 'File Operations',
    icon: '📁',
    description: 'Tools for working with files and documents',
    examples: [
      'read_file - Read file contents',
      'write_file - Create or update files',
      'list_directory - Browse file system',
      'analyze_document - Extract information'
    ],
    adapters: ['FileSystem', 'DocumentStore']
  },
  {
    name: 'External Services',
    icon: '🌐',
    description: 'Tools for integrating with external APIs and services',
    examples: [
      'web_search - Search the internet',
      'api_call - Make HTTP requests',
      'database_query - Query external databases',
      'weather_check - Get weather information'
    ],
    adapters: ['HTTP', 'Database', 'WebSearch']
  },
  {
    name: 'Analysis Tools',
    icon: '📊',
    description: 'Tools for data processing and analysis',
    examples: [
      'calculate - Perform calculations',
      'analyze_sentiment - Understand emotions',
      'extract_entities - Identify key information',
      'summarize - Create concise summaries'
    ],
    adapters: ['Analytics', 'NLP', 'DataProcessor']
  },
  {
    name: 'Control Tools',
    icon: '🎛️',
    description: 'Tools for system control and task management',
    examples: [
      'task_complete - Mark tasks as done',
      'defer - Postpone decisions',
      'ponder - Deep reflection',
      'reject - Decline inappropriate requests'
    ],
    adapters: ['Runtime', 'TaskScheduler']
  }
];

export default function ToolsPage() {
  const { hasRole } = useAuth();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [showArchitecture, setShowArchitecture] = useState(false);

  // Fetch available tools from API
  const { data: availableTools, isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: async () => {
      // TODO: Add tools endpoint to SDK when available
      // For now, return empty array
      return [];
    },
  });

  // Fetch adapter information
  const { data: adapters } = useQuery({
    queryKey: ['adapters'],
    queryFn: () => cirisClient.system.getAdapters(),
    enabled: hasRole('OBSERVER'),
  });

  const toolCount = availableTools?.length || 0;
  const adapterCount = adapters?.length || 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white shadow">
        <div className="px-4 py-5 sm:px-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">CIRIS Tool System</h2>
              <p className="mt-1 text-sm text-gray-500">
                Understanding the adapter-based tool architecture
              </p>
            </div>
            <button
              onClick={() => setShowArchitecture(!showArchitecture)}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              {showArchitecture ? 'Hide' : 'Show'} Architecture
            </button>
          </div>
        </div>
      </div>

      {/* Tool System Overview */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">How Tools Work in CIRIS</h3>
          <div className="prose max-w-none text-gray-600">
            <p className="mb-4">
              The CIRIS tool system is adapter-based, meaning tools are provided by different adapters 
              that connect CIRIS to various external systems and capabilities. This modular approach 
              allows for flexible deployment and customization.
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="text-3xl mb-2">🔌</div>
                <h4 className="font-semibold text-gray-900">Adapter-Provided</h4>
                <p className="text-sm mt-1">Tools come from loaded adapters, not hardcoded into the system</p>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <div className="text-3xl mb-2">🔄</div>
                <h4 className="font-semibold text-gray-900">Dynamic Loading</h4>
                <p className="text-sm mt-1">Tools become available when their adapters are activated</p>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="text-3xl mb-2">🎯</div>
                <h4 className="font-semibold text-gray-900">Context-Aware</h4>
                <p className="text-sm mt-1">Tools understand the channel and context they're called from</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Current System Status */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Current System Status</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="bg-gray-50 px-4 py-5 rounded-lg">
              <dt className="text-sm font-medium text-gray-500">Active Adapters</dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">{adapterCount}</dd>
            </div>
            <div className="bg-gray-50 px-4 py-5 rounded-lg">
              <dt className="text-sm font-medium text-gray-500">Available Tools</dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">{isLoading ? '...' : toolCount}</dd>
            </div>
            <div className="bg-gray-50 px-4 py-5 rounded-lg">
              <dt className="text-sm font-medium text-gray-500">Tool Categories</dt>
              <dd className="mt-1 text-3xl font-semibold text-gray-900">{toolCategories.length}</dd>
            </div>
            <div className="bg-gray-50 px-4 py-5 rounded-lg">
              <dt className="text-sm font-medium text-gray-500">Tool Bus Status</dt>
              <dd className="mt-1 text-xl font-semibold text-green-600 flex items-center">
                <span className="w-3 h-3 bg-green-500 rounded-full mr-2"></span>
                Operational
              </dd>
            </div>
          </div>
        </div>
      </div>

      {/* Architecture Diagram */}
      {showArchitecture && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Tool System Architecture</h3>
            <div className="bg-gray-50 rounded-lg p-6">
              <div className="space-y-4 font-mono text-sm">
                <div className="text-center">
                  <div className="inline-block bg-blue-100 px-4 py-2 rounded">CIRIS Core</div>
                </div>
                <div className="text-center">↓</div>
                <div className="text-center">
                  <div className="inline-block bg-green-100 px-4 py-2 rounded">Tool Bus</div>
                </div>
                <div className="text-center">↓</div>
                <div className="flex justify-center space-x-4">
                  <div className="bg-yellow-100 px-3 py-2 rounded">Discord Adapter</div>
                  <div className="bg-yellow-100 px-3 py-2 rounded">API Adapter</div>
                  <div className="bg-yellow-100 px-3 py-2 rounded">CLI Adapter</div>
                </div>
                <div className="text-center">↓</div>
                <div className="text-center">
                  <div className="inline-block bg-purple-100 px-4 py-2 rounded">Tool Implementations</div>
                </div>
              </div>
              <p className="mt-4 text-sm text-gray-600 text-center">
                Each adapter registers its tools with the Tool Bus, making them available system-wide
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tool Categories */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Tool Categories</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {toolCategories.map((category) => (
              <div
                key={category.name}
                className={`relative rounded-lg border-2 p-4 cursor-pointer transition-all ${
                  selectedCategory === category.name
                    ? 'border-indigo-500 bg-indigo-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => setSelectedCategory(
                  selectedCategory === category.name ? null : category.name
                )}
              >
                <div className="flex items-start">
                  <span className="text-2xl mr-3">{category.icon}</span>
                  <div className="flex-1">
                    <h4 className="text-base font-semibold text-gray-900">{category.name}</h4>
                    <p className="mt-1 text-sm text-gray-500">{category.description}</p>
                    {selectedCategory === category.name && (
                      <div className="mt-3 space-y-2">
                        <div>
                          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                            Example Tools:
                          </p>
                          <ul className="mt-1 text-sm text-gray-600 list-disc list-inside">
                            {category.examples.map((example) => (
                              <li key={example}>{example}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                            Provided By:
                          </p>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {category.adapters.map((adapter) => (
                              <span
                                key={adapter}
                                className="inline-block px-2 py-1 text-xs rounded-full bg-gray-200 text-gray-700"
                              >
                                {adapter}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Available Tools List */}
      {hasRole('OBSERVER') && availableTools && availableTools.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Currently Available Tools ({toolCount})
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {availableTools.map((tool: any) => (
                <div
                  key={tool.name}
                  className="bg-gray-50 rounded-lg p-3 border border-gray-200"
                >
                  <h4 className="font-medium text-gray-900">{tool.name}</h4>
                  {tool.description && (
                    <p className="mt-1 text-sm text-gray-600">{tool.description}</p>
                  )}
                  {tool.adapter && (
                    <p className="mt-1 text-xs text-gray-500">
                      Provided by: <span className="font-medium">{tool.adapter}</span>
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tool Usage Guide */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Using Tools in CIRIS</h3>
          <div className="space-y-4">
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h4 className="text-sm font-medium text-blue-800">Through Natural Language</h4>
                  <p className="mt-1 text-sm text-blue-700">
                    CIRIS understands your intent and automatically selects the right tools. 
                    Just describe what you need in plain language.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-green-50 border-l-4 border-green-400 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h4 className="text-sm font-medium text-green-800">Context-Aware Execution</h4>
                  <p className="mt-1 text-sm text-green-700">
                    Tools automatically receive context about the current channel, user, and conversation. 
                    No need to specify these details manually.
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h4 className="text-sm font-medium text-yellow-800">Safety and Validation</h4>
                  <p className="mt-1 text-sm text-yellow-700">
                    All tool executions are validated and logged. CIRIS ensures tools are used safely 
                    and appropriately based on permissions and context.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Role-based Information */}
      {hasRole('ADMIN') && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Administrator Information</h3>
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-semibold text-gray-900 mb-2">Tool Management</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li className="flex items-start">
                  <span className="text-green-500 mr-2">•</span>
                  Tools are registered automatically when adapters are loaded
                </li>
                <li className="flex items-start">
                  <span className="text-green-500 mr-2">•</span>
                  Use the Adapters page to manage which tool providers are active
                </li>
                <li className="flex items-start">
                  <span className="text-green-500 mr-2">•</span>
                  Tool permissions are enforced at the adapter level
                </li>
                <li className="flex items-start">
                  <span className="text-green-500 mr-2">•</span>
                  All tool executions are logged in the audit system
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
