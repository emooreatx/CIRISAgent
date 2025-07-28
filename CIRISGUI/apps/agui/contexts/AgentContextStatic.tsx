'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { cirisClient } from '../lib/ciris-sdk';
import type { APIRole, WARole } from '../lib/ciris-sdk';

// Static agent configuration
const STATIC_AGENTS = [
  {
    agent_id: 'datum',
    agent_name: 'Datum',
    status: 'running',
    health: 'healthy',
    api_url: process.env.NEXT_PUBLIC_CIRIS_API_URL || 'https://agents.ciris.ai',
    api_port: 8080,
  }
];

interface AgentInfo {
  agent_id: string;
  agent_name: string;
  status: string;
  health: string;
  api_url: string;
  api_port: number;
}

interface AgentRole {
  agentId: string;
  apiRole: APIRole;
  waRole?: WARole;
  isAuthority: boolean;
  lastChecked: Date;
}

interface AgentContextType {
  agents: AgentInfo[];
  currentAgent: AgentInfo | null;
  currentAgentRole: AgentRole | null;
  agentRoles: Map<string, AgentRole>;
  selectAgent: (agentId: string) => Promise<void>;
  refreshAgents: () => Promise<void>;
  refreshAgentRoles: () => Promise<void>;
  isLoadingAgents: boolean;
  isLoadingRoles: boolean;
  error: Error | null;
}

const AgentContext = createContext<AgentContextType | null>(null);

export function AgentProvider({ children }: { children: ReactNode }) {
  const [agents] = useState<AgentInfo[]>(STATIC_AGENTS);
  const [currentAgent, setCurrentAgent] = useState<AgentInfo | null>(STATIC_AGENTS[0]);
  const [agentRoles, setAgentRoles] = useState<Map<string, AgentRole>>(new Map());
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);
  const [isLoadingRoles, setIsLoadingRoles] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const { user } = useAuth();

  // Static agents - no discovery needed
  const refreshAgents = async () => {
    setIsLoadingAgents(true);
    setError(null);
    
    try {
      // For static configuration, just use the hardcoded list
      // No need to discover agents
      setIsLoadingAgents(false);
    } catch (err) {
      console.error('Error in refreshAgents:', err);
      setError(err as Error);
    } finally {
      setIsLoadingAgents(false);
    }
  };

  // Refresh role for a specific agent
  const refreshAgentRole = async (agent: AgentInfo) => {
    if (!user) return;

    try {
      // Point the client to the specific agent
      cirisClient.setBaseURL(`${agent.api_url}/api/${agent.agent_id}`);
      
      // Get current user info to determine roles
      const currentUser = await cirisClient.auth.getCurrentUser();
      
      const role: AgentRole = {
        agentId: agent.agent_id,
        apiRole: currentUser.role as APIRole,
        waRole: currentUser.wa_role as WARole | undefined,
        isAuthority: currentUser.role === 'AUTHORITY' || currentUser.role === 'SYSTEM_ADMIN',
        lastChecked: new Date()
      };
      
      setAgentRoles(prev => new Map(prev).set(agent.agent_id, role));
    } catch (err) {
      console.error(`Failed to get role for agent ${agent.agent_id}:`, err);
    }
  };

  // Refresh roles for all agents
  const refreshAgentRoles = async () => {
    if (!user || agents.length === 0) return;
    
    setIsLoadingRoles(true);
    setError(null);
    
    try {
      await Promise.all(agents.map(agent => refreshAgentRole(agent)));
    } catch (err) {
      console.error('Error refreshing agent roles:', err);
      setError(err as Error);
    } finally {
      setIsLoadingRoles(false);
    }
  };

  // Select an agent
  const selectAgent = async (agentId: string) => {
    const agent = agents.find(a => a.agent_id === agentId);
    if (!agent) {
      throw new Error(`Agent ${agentId} not found`);
    }
    
    setCurrentAgent(agent);
    
    // Update the SDK client to point to this agent
    cirisClient.setBaseURL(`${agent.api_url}/api/${agentId}`);
    
    // Refresh role for this agent
    if (user) {
      await refreshAgentRole(agent);
    }
  };

  // Initialize on mount
  useEffect(() => {
    refreshAgents();
  }, []);

  // Refresh roles when user changes
  useEffect(() => {
    if (user) {
      refreshAgentRoles();
    } else {
      setAgentRoles(new Map());
    }
  }, [user]);

  const currentAgentRole = currentAgent ? agentRoles.get(currentAgent.agent_id) || null : null;

  const value: AgentContextType = {
    agents,
    currentAgent,
    currentAgentRole,
    agentRoles,
    selectAgent,
    refreshAgents,
    refreshAgentRoles,
    isLoadingAgents,
    isLoadingRoles,
    error
  };

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}

export function useAgent() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgent must be used within AgentProvider');
  }
  return context;
}