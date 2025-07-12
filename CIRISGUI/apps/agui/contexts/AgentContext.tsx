'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AGENTS, AgentConfig } from '../config/agents';
import { useAuth } from './AuthContext';
import { cirisClient } from '../lib/ciris-sdk';
import type { APIRole, WARole } from '../lib/ciris-sdk';

interface AgentRole {
  agentId: string;
  apiRole: APIRole;
  waRole?: WARole;
  isAuthority: boolean;
  lastChecked: Date;
}

interface AgentContextType {
  agents: AgentConfig[];
  currentAgent: AgentConfig | null;
  currentAgentRole: AgentRole | null;
  agentRoles: Map<string, AgentRole>;
  selectAgent: (agentId: string) => Promise<void>;
  refreshAgentRoles: () => Promise<void>;
  isLoadingRoles: boolean;
}

const AgentContext = createContext<AgentContextType | null>(null);

export function AgentProvider({ children }: { children: ReactNode }) {
  const [currentAgent, setCurrentAgent] = useState<AgentConfig | null>(null);
  const [agentRoles, setAgentRoles] = useState<Map<string, AgentRole>>(new Map());
  const [isLoadingRoles, setIsLoadingRoles] = useState(false);
  const { user, token } = useAuth();

  // Initialize with first agent
  useEffect(() => {
    if (!currentAgent && AGENTS.length > 0) {
      setCurrentAgent(AGENTS[0]);
    }
  }, [currentAgent]);

  // Load agent roles when user logs in
  useEffect(() => {
    if (user && token) {
      refreshAgentRoles();
    }
  }, [user, token]);

  const refreshAgentRoles = async () => {
    if (!user || !token) return;
    
    setIsLoadingRoles(true);
    const newRoles = new Map<string, AgentRole>();

    // Check role on each agent
    for (const agent of AGENTS) {
      try {
        // Create a temporary client for this specific agent
        const agentClient = cirisClient.withConfig({
          baseURL: agent.apiUrl,
          authToken: token
        });

        // Get current user info from this agent
        const userInfo = await agentClient.auth.getCurrentUser();
        
        newRoles.set(agent.id, {
          agentId: agent.id,
          apiRole: userInfo.role as unknown as APIRole,
          waRole: userInfo.wa_role,
          isAuthority: userInfo.wa_role === 'authority' || userInfo.wa_role === 'root',
          lastChecked: new Date()
        });
      } catch (error) {
        console.error(`Failed to get role for agent ${agent.name}:`, error);
        // Default to observer if we can't reach the agent
        newRoles.set(agent.id, {
          agentId: agent.id,
          apiRole: 'OBSERVER' as APIRole,
          isAuthority: false,
          lastChecked: new Date()
        });
      }
    }

    setAgentRoles(newRoles);
    setIsLoadingRoles(false);
  };

  const selectAgent = async (agentId: string) => {
    const agent = AGENTS.find(a => a.id === agentId);
    if (!agent) return;

    setCurrentAgent(agent);
    
    // Update the SDK to use the new agent's API
    cirisClient.setConfig({
      baseURL: agent.apiUrl,
      authToken: token || undefined
    });

    // Refresh roles for this agent if needed
    const role = agentRoles.get(agentId);
    if (!role || (new Date().getTime() - role.lastChecked.getTime() > 300000)) { // 5 minutes
      await refreshAgentRoles();
    }
  };

  const currentAgentRole = currentAgent ? agentRoles.get(currentAgent.id) || null : null;

  return (
    <AgentContext.Provider value={{
      agents: AGENTS,
      currentAgent,
      currentAgentRole,
      agentRoles,
      selectAgent,
      refreshAgentRoles,
      isLoadingRoles
    }}>
      {children}
    </AgentContext.Provider>
  );
}

export function useAgent() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgent must be used within AgentProvider');
  }
  return context;
}