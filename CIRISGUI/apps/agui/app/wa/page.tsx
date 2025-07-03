'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cirisClient } from '../../lib/ciris-sdk';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';

interface Deferral {
  id: string;
  thought_id: string;
  reason: string;
  context: any;
  risk_assessment?: {
    level: 'low' | 'medium' | 'high' | 'critical';
    factors: string[];
  };
  ethical_considerations?: string[];
  timestamp: string;
  status: 'pending' | 'approved' | 'denied' | 'expired';
  resolution?: {
    decision: 'approve' | 'deny';
    reasoning: string;
    resolved_at: string;
    resolved_by: string;
  };
}

export default function WAPage() {
  const { user, hasRole } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedDeferral, setSelectedDeferral] = useState<Deferral | null>(null);
  const [resolutionModal, setResolutionModal] = useState(false);
  const [decision, setDecision] = useState<'approve' | 'deny'>('approve');
  const [reasoning, setReasoning] = useState('');
  const [filter, setFilter] = useState<'all' | 'pending' | 'resolved'>('pending');
  const [sortBy, setSortBy] = useState<'timestamp' | 'urgency' | 'type'>('timestamp');

  // Check authority access
  useEffect(() => {
    if (user && !hasRole('AUTHORITY')) {
      toast.error('Access denied. Authority role required.');
      router.push('/');
    }
  }, [user, hasRole, router]);

  // Fetch deferrals
  const { data: deferrals = [], isLoading } = useQuery({
    queryKey: ['deferrals'],
    queryFn: () => cirisClient.wiseAuthority.getDeferrals(),
    refetchInterval: 5000, // Refresh every 5 seconds
    enabled: hasRole('AUTHORITY'),
  });

  // Resolve deferral mutation
  const resolveMutation = useMutation({
    mutationFn: ({ id, decision, reasoning }: { id: string; decision: string; reasoning: string }) =>
      cirisClient.wiseAuthority.resolveDeferral(id, decision, reasoning),
    onSuccess: () => {
      toast.success('Deferral resolved successfully');
      queryClient.invalidateQueries({ queryKey: ['deferrals'] });
      setResolutionModal(false);
      setSelectedDeferral(null);
      setReasoning('');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to resolve deferral');
    },
  });

  // Filter deferrals
  const filteredDeferrals = deferrals.filter((d: Deferral) => {
    if (filter === 'all') return true;
    if (filter === 'pending') return d.status === 'pending';
    if (filter === 'resolved') return d.status === 'approved' || d.status === 'denied';
    return true;
  });

  // Sort deferrals
  const sortedDeferrals = [...filteredDeferrals].sort((a: Deferral, b: Deferral) => {
    if (sortBy === 'timestamp') {
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    }
    if (sortBy === 'urgency') {
      const urgencyOrder = { critical: 0, high: 1, medium: 2, low: 3 };
      const aUrgency = a.risk_assessment?.level || 'low';
      const bUrgency = b.risk_assessment?.level || 'low';
      return urgencyOrder[aUrgency] - urgencyOrder[bUrgency];
    }
    return 0;
  });

  // Stats calculation
  const stats = {
    total: deferrals.length,
    pending: deferrals.filter((d: Deferral) => d.status === 'pending').length,
    approved: deferrals.filter((d: Deferral) => d.status === 'approved').length,
    denied: deferrals.filter((d: Deferral) => d.status === 'denied').length,
    resolutionRate: deferrals.length > 0
      ? ((deferrals.filter((d: Deferral) => d.status === 'approved' || d.status === 'denied').length / deferrals.length) * 100).toFixed(1)
      : 0,
  };

  const getRiskColor = (level?: string) => {
    switch (level) {
      case 'critical': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      case 'low': return 'green';
      default: return 'gray';
    }
  };

  const getRiskBadgeClasses = (level?: string) => {
    switch (level) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusBadgeClasses = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-blue-100 text-blue-800';
      case 'approved': return 'bg-green-100 text-green-800';
      case 'denied': return 'bg-red-100 text-red-800';
      case 'expired': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const handleResolve = () => {
    if (!selectedDeferral || !reasoning.trim()) {
      toast.error('Please provide reasoning for your decision');
      return;
    }
    resolveMutation.mutate({
      id: selectedDeferral.id,
      decision,
      reasoning,
    });
  };

  if (!hasRole('AUTHORITY')) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white shadow">
        <div className="px-4 py-5 sm:px-6">
          <h2 className="text-2xl font-bold text-gray-900">Wise Authority Dashboard</h2>
          <p className="mt-1 text-sm text-gray-500">
            Review and resolve deferred decisions requiring authority oversight
          </p>
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Total Deferrals</dt>
            <dd className="mt-1 text-3xl font-semibold text-gray-900">{stats.total}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Pending</dt>
            <dd className="mt-1 text-3xl font-semibold text-blue-600">{stats.pending}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Approved</dt>
            <dd className="mt-1 text-3xl font-semibold text-green-600">{stats.approved}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Denied</dt>
            <dd className="mt-1 text-3xl font-semibold text-red-600">{stats.denied}</dd>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <dt className="text-sm font-medium text-gray-500 truncate">Resolution Rate</dt>
            <dd className="mt-1 text-3xl font-semibold text-gray-900">{stats.resolutionRate}%</dd>
          </div>
        </div>
      </div>

      {/* Filters and Controls */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center space-x-4">
              <label className="text-sm font-medium text-gray-700">Filter:</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as any)}
                className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="all">All Deferrals</option>
                <option value="pending">Pending Only</option>
                <option value="resolved">Resolved Only</option>
              </select>
            </div>
            <div className="flex items-center space-x-4">
              <label className="text-sm font-medium text-gray-700">Sort by:</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              >
                <option value="timestamp">Date (Newest First)</option>
                <option value="urgency">Urgency (Critical First)</option>
                <option value="type">Type</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Deferrals List */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Deferred Decisions</h3>
          
          {isLoading ? (
            <div className="text-center py-8">
              <p className="text-gray-500">Loading deferrals...</p>
            </div>
          ) : sortedDeferrals.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500">No deferrals found matching your criteria.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {sortedDeferrals.map((deferral: Deferral) => (
                <div
                  key={deferral.id}
                  className={`border rounded-lg p-4 hover:shadow-lg transition-shadow cursor-pointer ${
                    selectedDeferral?.id === deferral.id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200'
                  }`}
                  onClick={() => setSelectedDeferral(deferral)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h4 className="text-sm font-semibold text-gray-900">
                          Thought ID: {deferral.thought_id}
                        </h4>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeClasses(deferral.status)}`}>
                          {deferral.status.toUpperCase()}
                        </span>
                        {deferral.risk_assessment && (
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getRiskBadgeClasses(deferral.risk_assessment.level)}`}>
                            {deferral.risk_assessment.level.toUpperCase()} RISK
                          </span>
                        )}
                      </div>
                      
                      <p className="text-sm text-gray-600 mb-2">{deferral.reason}</p>
                      
                      <div className="flex items-center text-xs text-gray-500 space-x-4">
                        <span>{new Date(deferral.timestamp).toLocaleString()}</span>
                        {deferral.ethical_considerations && deferral.ethical_considerations.length > 0 && (
                          <span>{deferral.ethical_considerations.length} ethical considerations</span>
                        )}
                      </div>
                      
                      {deferral.resolution && (
                        <div className="mt-3 p-3 bg-gray-50 rounded-md">
                          <p className="text-xs font-medium text-gray-700">
                            Resolution: <span className={deferral.resolution.decision === 'approve' ? 'text-green-600' : 'text-red-600'}>
                              {deferral.resolution.decision.toUpperCase()}
                            </span>
                          </p>
                          <p className="text-xs text-gray-600 mt-1">{deferral.resolution.reasoning}</p>
                          <p className="text-xs text-gray-500 mt-1">
                            by {deferral.resolution.resolved_by} at {new Date(deferral.resolution.resolved_at).toLocaleString()}
                          </p>
                        </div>
                      )}
                    </div>
                    
                    {deferral.status === 'pending' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedDeferral(deferral);
                          setResolutionModal(true);
                        }}
                        className="ml-4 inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                      >
                        Resolve
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Selected Deferral Details */}
      {selectedDeferral && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Deferral Details</h3>
            
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium text-gray-700">Context</h4>
                <pre className="mt-1 text-sm text-gray-600 bg-gray-50 p-3 rounded-md overflow-x-auto">
                  {JSON.stringify(selectedDeferral.context, null, 2)}
                </pre>
              </div>
              
              {selectedDeferral.risk_assessment && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700">Risk Assessment</h4>
                  <div className="mt-1">
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border-2 ${getRiskBadgeClasses(selectedDeferral.risk_assessment.level)}`}>
                      {selectedDeferral.risk_assessment.level.toUpperCase()} RISK
                    </span>
                    <ul className="mt-2 list-disc list-inside text-sm text-gray-600">
                      {selectedDeferral.risk_assessment.factors.map((factor, idx) => (
                        <li key={idx}>{factor}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
              
              {selectedDeferral.ethical_considerations && selectedDeferral.ethical_considerations.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700">Ethical Considerations</h4>
                  <ul className="mt-1 list-disc list-inside text-sm text-gray-600">
                    {selectedDeferral.ethical_considerations.map((consideration, idx) => (
                      <li key={idx}>{consideration}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Resolution Modal */}
      {resolutionModal && selectedDeferral && (
        <div className="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true"></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full sm:p-6">
              <div>
                <div className="text-center">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Resolve Deferral
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Review the deferral and provide your decision with reasoning.
                    </p>
                  </div>
                </div>
                <div className="mt-5">
                  <div className="mb-4">
                    <label className="text-sm font-medium text-gray-700">Decision</label>
                    <div className="mt-2 space-x-4">
                      <label className="inline-flex items-center">
                        <input
                          type="radio"
                          className="form-radio text-green-600"
                          value="approve"
                          checked={decision === 'approve'}
                          onChange={(e) => setDecision(e.target.value as 'approve')}
                        />
                        <span className="ml-2 text-sm text-gray-700">Approve</span>
                      </label>
                      <label className="inline-flex items-center">
                        <input
                          type="radio"
                          className="form-radio text-red-600"
                          value="deny"
                          checked={decision === 'deny'}
                          onChange={(e) => setDecision(e.target.value as 'deny')}
                        />
                        <span className="ml-2 text-sm text-gray-700">Deny</span>
                      </label>
                    </div>
                  </div>
                  
                  <div>
                    <label htmlFor="reasoning" className="block text-sm font-medium text-gray-700">
                      Reasoning
                    </label>
                    <div className="mt-1">
                      <textarea
                        id="reasoning"
                        rows={4}
                        className="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                        placeholder="Provide detailed reasoning for your decision..."
                        value={reasoning}
                        onChange={(e) => setReasoning(e.target.value)}
                      />
                    </div>
                    <p className="mt-2 text-sm text-gray-500">
                      Your reasoning will be recorded and may be used for future guidance.
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  onClick={handleResolve}
                  disabled={!reasoning.trim() || resolveMutation.isPending}
                  className={`w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-base font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 sm:col-start-2 sm:text-sm ${
                    decision === 'approve'
                      ? 'bg-green-600 hover:bg-green-700 focus:ring-green-500'
                      : 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {resolveMutation.isPending ? 'Resolving...' : `${decision === 'approve' ? 'Approve' : 'Deny'} Deferral`}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setResolutionModal(false);
                    setReasoning('');
                  }}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:col-start-1 sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
