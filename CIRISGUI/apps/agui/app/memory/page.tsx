'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../lib/api-client-v1';
import toast from 'react-hot-toast';
import { debounce } from 'lodash';

interface MemoryNode {
  id: string;
  node_type: string;
  properties: Record<string, any>;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

interface MemoryStats {
  total_nodes: number;
  nodes_by_type: Record<string, number>;
  total_relationships: number;
  memory_size_bytes: number;
  oldest_node: string;
  newest_node: string;
}

export default function MemoryPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<MemoryNode | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const queryClient = useQueryClient();

  // Fetch memory statistics
  const { data: stats, isLoading: statsLoading } = useQuery<MemoryStats>({
    queryKey: ['memory-stats'],
    queryFn: () => apiClient.getMemoryStats(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Search memory nodes
  const { data: searchResults, isLoading: searchLoading } = useQuery<MemoryNode[]>({
    queryKey: ['memory-search', searchQuery],
    queryFn: () => apiClient.queryMemory(searchQuery, 20),
    enabled: searchQuery.length > 0,
  });

  // Debounced search
  const debouncedSearch = useCallback(
    debounce((query: string) => {
      setSearchQuery(query);
      setIsSearching(false);
    }, 300),
    []
  );

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setIsSearching(true);
    debouncedSearch(query);
  };

  // Load selected node details
  const loadNodeDetails = async (nodeId: string) => {
    try {
      const node = await apiClient.getMemoryNode(nodeId);
      setSelectedNode(node);
    } catch (error) {
      toast.error('Failed to load node details');
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getNodeTypeColor = (nodeType: string) => {
    const colors: Record<string, string> = {
      'thought': 'bg-blue-100 text-blue-800',
      'task': 'bg-green-100 text-green-800',
      'memory': 'bg-purple-100 text-purple-800',
      'observation': 'bg-yellow-100 text-yellow-800',
      'decision': 'bg-red-100 text-red-800',
      'metric': 'bg-gray-100 text-gray-800',
    };
    return colors[nodeType.toLowerCase()] || 'bg-gray-100 text-gray-800';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h1 className="text-2xl font-bold text-gray-900">Memory Graph</h1>
          <p className="mt-2 text-gray-600">
            Search and explore the agent's memory nodes and relationships
          </p>
        </div>
      </div>

      {/* Memory Statistics */}
      {stats && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Memory Statistics</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg">
                <dt className="text-sm font-medium text-gray-500">Total Nodes</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">
                  {stats.total_nodes.toLocaleString()}
                </dd>
              </div>
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg">
                <dt className="text-sm font-medium text-gray-500">Total Relationships</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">
                  {stats.total_relationships.toLocaleString()}
                </dd>
              </div>
              <div className="bg-gray-50 px-4 py-5 sm:p-6 rounded-lg">
                <dt className="text-sm font-medium text-gray-500">Memory Size</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">
                  {formatBytes(stats.memory_size_bytes)}
                </dd>
              </div>
            </div>
            
            {/* Node Type Breakdown */}
            <div className="mt-6">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Nodes by Type</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.nodes_by_type).map(([type, count]) => (
                  <span
                    key={type}
                    className={`inline-flex items-center rounded-md px-3 py-1 text-sm font-medium ${getNodeTypeColor(type)}`}
                  >
                    {type}: {count}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search Section */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Search Memory</h2>
          <div className="relative">
            <input
              type="text"
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              placeholder="Search for thoughts, tasks, observations..."
              onChange={handleSearchChange}
            />
            {(isSearching || searchLoading) && (
              <div className="absolute right-3 top-2">
                <svg className="animate-spin h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Search Results */}
      {searchResults && searchResults.length > 0 && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Search Results ({searchResults.length})
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {searchResults.map((node) => (
                <div
                  key={node.id}
                  className="relative rounded-lg border border-gray-300 bg-white px-4 py-5 shadow-sm hover:border-gray-400 cursor-pointer transition-colors"
                  onClick={() => loadNodeDetails(node.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${getNodeTypeColor(node.node_type)}`}>
                        {node.node_type}
                      </span>
                      <p className="mt-2 text-sm text-gray-900 line-clamp-3">
                        {node.properties.content || node.properties.description || node.properties.name || 'No content'}
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        {formatDate(node.created_at)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Selected Node Details */}
      {selectedNode && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">Node Details</h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-400 hover:text-gray-500"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              {/* Node Info */}
              <div>
                <h4 className="text-sm font-medium text-gray-700">Node Information</h4>
                <dl className="mt-2 border-t border-gray-200 divide-y divide-gray-200">
                  <div className="py-3 flex justify-between text-sm">
                    <dt className="text-gray-500">ID</dt>
                    <dd className="text-gray-900 font-mono text-xs">{selectedNode.id}</dd>
                  </div>
                  <div className="py-3 flex justify-between text-sm">
                    <dt className="text-gray-500">Type</dt>
                    <dd className="text-gray-900">
                      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ${getNodeTypeColor(selectedNode.node_type)}`}>
                        {selectedNode.node_type}
                      </span>
                    </dd>
                  </div>
                  <div className="py-3 flex justify-between text-sm">
                    <dt className="text-gray-500">Created</dt>
                    <dd className="text-gray-900">{formatDate(selectedNode.created_at)}</dd>
                  </div>
                  <div className="py-3 flex justify-between text-sm">
                    <dt className="text-gray-500">Updated</dt>
                    <dd className="text-gray-900">{formatDate(selectedNode.updated_at)}</dd>
                  </div>
                </dl>
              </div>

              {/* Node Properties */}
              <div>
                <h4 className="text-sm font-medium text-gray-700">Properties</h4>
                <div className="mt-2 bg-gray-50 rounded-lg p-4">
                  <pre className="text-xs text-gray-900 whitespace-pre-wrap">
                    {JSON.stringify(selectedNode.properties, null, 2)}
                  </pre>
                </div>
              </div>

              {/* Node Metadata */}
              {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700">Metadata</h4>
                  <div className="mt-2 bg-gray-50 rounded-lg p-4">
                    <pre className="text-xs text-gray-900 whitespace-pre-wrap">
                      {JSON.stringify(selectedNode.metadata, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {searchQuery && searchResults && searchResults.length === 0 && !searchLoading && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
            <p className="mt-1 text-sm text-gray-500">
              Try searching with different keywords
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
