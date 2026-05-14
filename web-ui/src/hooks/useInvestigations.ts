import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Investigation, InvestigationStatus, AlertSeverity, Action, ActionStatus, TimelineEvent } from '@/types';

// ==================== Types ====================
export interface InvestigationFilters {
  status?: InvestigationStatus;
  severity?: AlertSeverity;
  alertId?: string;
}

export interface ApproveActionParams {
  investigationId: string;
  stepId: string;
  feedback?: string;
}

export interface RejectActionParams {
  investigationId: string;
  stepId: string;
  reason: string;
}

// ==================== Query Keys ====================
export const investigationKeys = {
  all: ['investigations'] as const,
  lists: () => [...investigationKeys.all, 'list'] as const,
  list: (filters?: InvestigationFilters) => [...investigationKeys.lists(), filters] as const,
  details: () => [...investigationKeys.all, 'detail'] as const,
  detail: (id: string) => [...investigationKeys.details(), id] as const,
  steps: (id: string) => [...investigationKeys.detail(id), 'steps'] as const,
  timeline: (id: string) => [...investigationKeys.detail(id), 'timeline'] as const,
};

// ==================== Queries ====================

/**
 * Fetch all investigations with optional filters
 * Auto-refetches every 5 seconds for real-time updates
 */
export function useInvestigations(filters?: InvestigationFilters) {
  return useQuery({
    queryKey: investigationKeys.list(filters),
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (filters?.status) params.status = filters.status;
      if (filters?.severity) params.severity = filters.severity;
      if (filters?.alertId) params.alertId = filters.alertId;
      
      return api.get<Investigation[]>('/v1/investigations', Object.keys(params).length > 0 ? params : undefined);
    },
    refetchInterval: 5000,
    staleTime: 2000,
  });
}

/**
 * Fetch a single investigation by ID
 * Polls more frequently (3s) for active investigations
 */
export function useInvestigation(id: string) {
  return useQuery({
    queryKey: investigationKeys.detail(id),
    queryFn: () => api.get<Investigation>(`/v1/investigations/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      // Poll more frequently for active investigations
      const data = query.state.data;
      if (data && ['pending', 'in_progress', 'waiting_approval'].includes(data.status)) {
        return 3000;
      }
      return false; // Stop polling for completed/failed
    },
    staleTime: 1000,
  });
}

/**
 * Fetch investigation timeline for display
 * Returns timeline events from the investigation
 * Polls when investigation is active
 */
export function useInvestigationTimeline(id: string) {
  const queryClient = useQueryClient();
  
  return useQuery({
    queryKey: investigationKeys.timeline(id),
    queryFn: async () => {
      const investigation = await api.get<Investigation>(`/v1/investigations/${id}`);
      return investigation.timeline || [];
    },
    enabled: !!id,
    select: (data): TimelineEvent[] => data,
    refetchInterval: () => {
      // Check if the parent investigation is active
      const investigation = queryClient.getQueryData<Investigation>(investigationKeys.detail(id));
      if (investigation && ['pending', 'in_progress', 'waiting_approval'].includes(investigation.status)) {
        return 3000;
      }
      return false;
    },
    staleTime: 1000,
  });
}

/**
 * Fetch active investigations count for dashboard
 */
export function useActiveInvestigationsCount() {
  return useQuery({
    queryKey: [...investigationKeys.lists(), 'count', 'active'],
    queryFn: async () => {
      const investigations = await api.get<Investigation[]>('/v1/investigations', { 
        status: 'in_progress' 
      });
      return investigations.length;
    },
    refetchInterval: 10000,
  });
}

// ==================== Mutations ====================

/**
 * Approve a pending action in an investigation
 * Optimistically updates the step status
 */
export function useApproveAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ investigationId, stepId, feedback }: ApproveActionParams) =>
      api.post(`/v1/investigations/${investigationId}/steps/${stepId}/approve`, { feedback }),
    
    onMutate: async ({ investigationId, stepId }) => {
      await queryClient.cancelQueries({ queryKey: investigationKeys.detail(investigationId) });
      
      const previousInvestigation = queryClient.getQueryData<Investigation>(
        investigationKeys.detail(investigationId)
      );
      
      // Optimistically update the action status
      if (previousInvestigation) {
        queryClient.setQueryData<Investigation>(
          investigationKeys.detail(investigationId),
          {
            ...previousInvestigation,
            actions: previousInvestigation.actions.map((action: Action) =>
              action.id === stepId 
                ? { ...action, status: 'executing' as ActionStatus }
                : action
            ),
          }
        );
      }

      return { previousInvestigation };
    },
    
    onError: (_err, { investigationId }, context) => {
      if (context?.previousInvestigation) {
        queryClient.setQueryData(
          investigationKeys.detail(investigationId),
          context.previousInvestigation
        );
      }
    },
    
    onSettled: (_data, _err, { investigationId }) => {
      queryClient.invalidateQueries({ queryKey: investigationKeys.detail(investigationId) });
      queryClient.invalidateQueries({ queryKey: investigationKeys.lists() });
    },
  });
}

/**
 * Reject a pending action in an investigation
 * Requires a reason for rejection
 */
export function useRejectAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ investigationId, stepId, reason }: RejectActionParams) =>
      api.post(`/v1/investigations/${investigationId}/steps/${stepId}/reject`, { reason }),
    
    onMutate: async ({ investigationId, stepId }) => {
      await queryClient.cancelQueries({ queryKey: investigationKeys.detail(investigationId) });
      
      const previousInvestigation = queryClient.getQueryData<Investigation>(
        investigationKeys.detail(investigationId)
      );
      
      // Optimistically update the action status
      if (previousInvestigation) {
        queryClient.setQueryData<Investigation>(
          investigationKeys.detail(investigationId),
          {
            ...previousInvestigation,
            actions: previousInvestigation.actions.map((action: Action) =>
              action.id === stepId 
                ? { ...action, status: 'rejected' as ActionStatus }
                : action
            ),
          }
        );
      }

      return { previousInvestigation };
    },
    
    onError: (_err, { investigationId }, context) => {
      if (context?.previousInvestigation) {
        queryClient.setQueryData(
          investigationKeys.detail(investigationId),
          context.previousInvestigation
        );
      }
    },
    
    onSettled: (_data, _err, { investigationId }) => {
      queryClient.invalidateQueries({ queryKey: investigationKeys.detail(investigationId) });
      queryClient.invalidateQueries({ queryKey: investigationKeys.lists() });
    },
  });
}

/**
 * Cancel an in-progress investigation
 */
export function useCancelInvestigation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.post(`/v1/investigations/${id}/cancel`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: investigationKeys.detail(id) });
      
      const previousInvestigation = queryClient.getQueryData<Investigation>(
        investigationKeys.detail(id)
      );
      
      if (previousInvestigation) {
        queryClient.setQueryData<Investigation>(
          investigationKeys.detail(id),
          {
            ...previousInvestigation,
            status: 'failed',
            completedAt: new Date().toISOString(),
          }
        );
      }

      return { previousInvestigation };
    },
    
    onError: (_err, id, context) => {
      if (context?.previousInvestigation) {
        queryClient.setQueryData(investigationKeys.detail(id), context.previousInvestigation);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: investigationKeys.all });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

/**
 * Retry a failed investigation
 */
export function useRetryInvestigation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.post<Investigation>(`/v1/investigations/${id}/retry`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: investigationKeys.detail(id) });
      
      const previousInvestigation = queryClient.getQueryData<Investigation>(
        investigationKeys.detail(id)
      );
      
      if (previousInvestigation) {
        queryClient.setQueryData<Investigation>(
          investigationKeys.detail(id),
          {
            ...previousInvestigation,
            status: 'pending',
            completedAt: undefined,
          }
        );
      }

      return { previousInvestigation };
    },
    
    onError: (_err, id, context) => {
      if (context?.previousInvestigation) {
        queryClient.setQueryData(investigationKeys.detail(id), context.previousInvestigation);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: investigationKeys.all });
    },
  });
}

/**
 * Add manual feedback/context to an investigation
 */
export function useAddInvestigationContext() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, context }: { id: string; context: string }) =>
      api.post(`/v1/investigations/${id}/context`, { context }),
    
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: investigationKeys.detail(id) });
    },
  });
}
