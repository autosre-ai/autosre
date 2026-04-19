'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Investigation, Agent, Skill, Runbook, Metrics, SystemStatus } from '@/lib/api';

// System
export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: ['system-status'],
    queryFn: api.getStatus,
    refetchInterval: 10000,
  });
}

export function useMetrics() {
  return useQuery<Metrics>({
    queryKey: ['metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 5000,
  });
}

// Investigations (Incidents)
export function useInvestigations() {
  return useQuery<Investigation[]>({
    queryKey: ['investigations'],
    queryFn: api.getInvestigations,
    refetchInterval: 5000,
  });
}

export function useInvestigation(id: string) {
  return useQuery<Investigation>({
    queryKey: ['investigation', id],
    queryFn: () => api.getInvestigation(id),
    refetchInterval: 3000,
    enabled: !!id,
  });
}

export function useCreateInvestigation() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: { issue: string; namespace: string }) =>
      api.createInvestigation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}

export function useApproveAction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ investigationId, actionId }: { investigationId: string; actionId: string }) =>
      api.approveAction(investigationId, actionId),
    onSuccess: (_, { investigationId }) => {
      queryClient.invalidateQueries({ queryKey: ['investigation', investigationId] });
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}

export function useRejectAction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ investigationId, actionId, reason }: { investigationId: string; actionId: string; reason: string }) =>
      api.rejectAction(investigationId, actionId, reason),
    onSuccess: (_, { investigationId }) => {
      queryClient.invalidateQueries({ queryKey: ['investigation', investigationId] });
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}

// Agents
export function useAgents() {
  return useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: api.getAgents,
    refetchInterval: 10000,
  });
}

export function useAgent(id: string) {
  return useQuery<Agent>({
    queryKey: ['agent', id],
    queryFn: () => api.getAgent(id),
    refetchInterval: 5000,
    enabled: !!id,
  });
}

export function useDeployAgent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.deployAgent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}

export function useStopAgent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.stopAgent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}

// Skills
export function useSkills() {
  return useQuery<Skill[]>({
    queryKey: ['skills'],
    queryFn: api.getSkills,
    staleTime: 60000,
  });
}

export function useSkill(id: string) {
  return useQuery<Skill>({
    queryKey: ['skill', id],
    queryFn: () => api.getSkill(id),
    enabled: !!id,
  });
}

// Runbooks
export function useRunbooks() {
  return useQuery<Runbook[]>({
    queryKey: ['runbooks'],
    queryFn: api.getRunbooks,
    refetchInterval: 30000,
  });
}

export function useRunbook(id: string) {
  return useQuery<Runbook>({
    queryKey: ['runbook', id],
    queryFn: () => api.getRunbook(id),
    enabled: !!id,
  });
}

export function useExecuteRunbook() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, params }: { id: string; params?: Record<string, unknown> }) =>
      api.executeRunbook(id, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbooks'] });
    },
  });
}
