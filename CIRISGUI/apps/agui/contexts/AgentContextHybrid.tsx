'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { cirisClient } from '../lib/ciris-sdk';
import { AgentInfo } from '../lib/ciris-sdk/resources/manager';
import type { APIRole, WARole } from '../lib/ciris-sdk';

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
  isManagerAvailable: boolean;
}

const AgentContext = createContext<AgentContextType | null>(null);

// Default local dev agent when manager is not available
const DEFAULT_LOCAL_AGENT: AgentInfo = {
  agent_id: 'datum',
  agent_name: 'Datum (Local Dev)',
  status: 'running',
  health: 'healthy',
  api_url: process.env.NEXT_PUBLIC_CIRIS_API_URL || 'http://localhost',
  api_port: 8080,
  container_name: 'ciris-agent-datum',
  image: 'ciris-agent:latest',
  created_at: new Date().toISOString(),
  started_at: new Date().toISOString(),
  template_id: 'echo',
  git_repo: null,
  git_branch: null,
  env_vars: {},
  volumes: [],
  networks: ['ciris-network'],
  restart: 'unless-stopped',
  update_available: false,
  exit_code: null,
  capabilities: {
    api: true,
    discord: true,
    cli: true
  }
};

export function AgentProvider({ children }: { children: ReactNode }) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [currentAgent, setCurrentAgent] = useState<AgentInfo | null>(null);
  const [agentRoles, setAgentRoles] = useState<Map<string, AgentRole>>(new Map());
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);
  const [isLoadingRoles, setIsLoadingRoles] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isManagerAvailable, setIsManagerAvailable] = useState(false);
  const { user } = useAuth();

  // Discover agents from CIRISManager or fallback to local
  const refreshAgents = async () => {
    setIsLoadingAgents(true);
    setError(null);
    
    try {
      // Try to fetch from manager first
      const discovered = await cirisClient.manager.listAgents();
      setAgents(discovered);
      setIsManagerAvailable(true);
      
      // If no current agent selected, select first running agent
      if (!currentAgent && discovered.length > 0) {
        const runningAgent = discovered.find(a => a.status === 'running') || discovered[0];
        await selectAgent(runningAgent.agent_id);
      }
    } catch (err) {
      // Manager not available, use default local agent
      console.log('CIRIS Manager not available, using local dev agent');
      setAgents([DEFAULT_LOCAL_AGENT]);
      setIsManagerAvailable(false);
      
      // Auto-select the default agent
      if (!currentAgent) {
        await selectAgent(DEFAULT_LOCAL_AGENT.agent_id);
      }
      
      // Only set error if it's not a connection error (which is expected)
      if (err instanceof Error && !err.message.includes('fetch') && !err.message.includes('Failed to fetch')) {
        setError(err);
      }
    } finally {
      setIsLoadingAgents(false);
    }
  };

  // Fetch roles for all agents
  const refreshAgentRoles = async () => {
    if (!user) return;
    
    setIsLoadingRoles(true);
    const newRoles = new Map<string, AgentRole>();
    
    for (const agent of agents) {
      try {
        // Configure client for this specific agent
        const agentUrl = isManagerAvailable 
          ? `${window.location.origin}/api/${agent.agent_id}`
          : `${agent.api_url}:${agent.api_port}`;
        
        cirisClient.setConfig({ baseURL: agentUrl });
        
        // Get current user info for this agent
        const userInfo = await cirisClient.auth.getCurrentUser();
        
        newRoles.set(agent.agent_id, {
          agentId: agent.agent_id,
          apiRole: userInfo.api_role,
          waRole: userInfo.wa_role,
          isAuthority: userInfo.is_authority || false,
          lastChecked: new Date()
        });
      } catch (error) {
        console.error(`Failed to fetch role for agent ${agent.agent_id}:`, error);
        // Set a default role on error
        newRoles.set(agent.agent_id, {
          agentId: agent.agent_id,
          apiRole: 'OBSERVER' as APIRole,
          isAuthority: false,
          lastChecked: new Date()
        });
      }
    }
    
    setAgentRoles(newRoles);
    setIsLoadingRoles(false);
  };

  // Select an agent
  const selectAgent = async (agentId: string) => {
    const agent = agents.find(a => a.agent_id === agentId);
    if (!agent) return;
    
    setCurrentAgent(agent);
    
    // Update API client base URL for the selected agent
    const agentUrl = isManagerAvailable 
      ? `${window.location.origin}/api/${agent.agent_id}`
      : `${agent.api_url}:${agent.api_port}`;
    
    cirisClient.setConfig({ baseURL: agentUrl });
    
    // Store selection
    localStorage.setItem('selectedAgentId', agentId);
    localStorage.setItem('selectedAgentName', agent.agent_name);
  };

  // Get current agent role
  const currentAgentRole = currentAgent ? agentRoles.get(currentAgent.agent_id) || null : null;

  // Initial load
  useEffect(() => {
    refreshAgents();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh roles when agents or user changes
  useEffect(() => {
    if (agents.length > 0 && user) {
      refreshAgentRoles();
    }
  }, [agents, user]); // eslint-disable-line react-hooks/exhaustive-deps

  // Restore previous selection
  useEffect(() => {
    const savedAgentId = localStorage.getItem('selectedAgentId');
    if (savedAgentId && agents.length > 0 && !currentAgent) {
      selectAgent(savedAgentId);
    }
  }, [agents]); // eslint-disable-line react-hooks/exhaustive-deps

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
    error,
    isManagerAvailable,
  };

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>;
}

export function useAgent() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgent must be used within an AgentProvider');
  }
  return context;
}