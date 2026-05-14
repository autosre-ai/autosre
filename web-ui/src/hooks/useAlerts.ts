import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Alert, AlertSeverity, AlertStatus, Investigation, AlertFilter } from '@/types';

// ==================== Types ====================
export type AlertFilters = Partial<Omit<AlertFilter, 'severity' | 'status' | 'source' | 'service'> & {
  severity?: AlertSeverity;
  status?: AlertStatus;
  source?: string;
  service?: string;
}>;

export interface SilenceAlertParams {
  id: string;
  duration: number;
  reason?: string;
}

// ==================== Query Keys ====================
export const alertKeys = {
  all: ['alerts'] as const,
  lists: () => [...alertKeys.all, 'list'] as const,
  list: (filters?: AlertFilters) => [...alertKeys.lists(), filters] as const,
  details: () => [...alertKeys.all, 'detail'] as const,
  detail: (id: string) => [...alertKeys.details(), id] as const,
};

// ==================== Queries ====================

/**
 * Fetch all alerts with optional filters
 * Auto-refetches every 10 seconds for real-time updates
 */
export function useAlerts(filters?: AlertFilters) {
  return useQuery({
    queryKey: alertKeys.list(filters),
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (filters?.severity) params.severity = filters.severity;
      if (filters?.status) params.status = filters.status;
      if (filters?.service) params.service = filters.service;
      if (filters?.cluster) params.cluster = filters.cluster;
      if (filters?.source) params.source = filters.source;
      if (filters?.search) params.search = filters.search;
      
      return api.get<Alert[]>('/v1/alerts', Object.keys(params).length > 0 ? params : undefined);
    },
    refetchInterval: 10000,
    staleTime: 5000,
  });
}

/**
 * Fetch a single alert by ID
 */
export function useAlert(id: string) {
  return useQuery({
    queryKey: alertKeys.detail(id),
    queryFn: () => api.get<Alert>(`/v1/alerts/${id}`),
    enabled: !!id,
    staleTime: 5000,
  });
}

// ==================== Mutations ====================

/**
 * Acknowledge an alert
 * Optimistically updates the alert status in cache
 */
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.post<Alert>(`/v1/alerts/${id}/acknowledge`),
    
    // Optimistic update
    onMutate: async (id) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: alertKeys.all });
      
      // Snapshot previous value
      const previousAlert = queryClient.getQueryData<Alert>(alertKeys.detail(id));
      
      // Optimistically update the alert
      if (previousAlert) {
        queryClient.setQueryData<Alert>(alertKeys.detail(id), {
          ...previousAlert,
          status: 'acknowledged',
        });
      }
      
      // Update in list cache
      queryClient.setQueriesData<Alert[]>(
        { queryKey: alertKeys.lists() },
        (old) => old?.map(alert => 
          alert.id === id ? { ...alert, status: 'acknowledged' as AlertStatus } : alert
        )
      );

      return { previousAlert };
    },
    
    onError: (_err, id, context) => {
      // Rollback on error
      if (context?.previousAlert) {
        queryClient.setQueryData(alertKeys.detail(id), context.previousAlert);
      }
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

/**
 * Resolve an alert
 * Optimistically updates the alert status to resolved
 */
export function useResolveAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.post<Alert>(`/v1/alerts/${id}/resolve`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: alertKeys.all });
      
      const previousAlert = queryClient.getQueryData<Alert>(alertKeys.detail(id));
      
      if (previousAlert) {
        queryClient.setQueryData<Alert>(alertKeys.detail(id), {
          ...previousAlert,
          status: 'resolved',
          resolvedAt: new Date().toISOString(),
        });
      }
      
      queryClient.setQueriesData<Alert[]>(
        { queryKey: alertKeys.lists() },
        (old) => old?.map(alert => 
          alert.id === id 
            ? { ...alert, status: 'resolved' as AlertStatus, resolvedAt: new Date().toISOString() } 
            : alert
        )
      );

      return { previousAlert };
    },
    
    onError: (_err, id, context) => {
      if (context?.previousAlert) {
        queryClient.setQueryData(alertKeys.detail(id), context.previousAlert);
      }
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

/**
 * Silence an alert for a specific duration
 */
export function useSilenceAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, duration, reason }: SilenceAlertParams) =>
      api.post<Alert>(`/v1/alerts/${id}/silence`, { duration, reason }),
    
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: alertKeys.all });
      
      const previousAlert = queryClient.getQueryData<Alert>(alertKeys.detail(id));
      
      if (previousAlert) {
        queryClient.setQueryData<Alert>(alertKeys.detail(id), {
          ...previousAlert,
          status: 'silenced',
        });
      }
      
      queryClient.setQueriesData<Alert[]>(
        { queryKey: alertKeys.lists() },
        (old) => old?.map(alert => 
          alert.id === id ? { ...alert, status: 'silenced' as AlertStatus } : alert
        )
      );

      return { previousAlert };
    },
    
    onError: (_err, { id }, context) => {
      if (context?.previousAlert) {
        queryClient.setQueryData(alertKeys.detail(id), context.previousAlert);
      }
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

/**
 * Start an AI investigation for an alert
 * Returns the created investigation
 */
export function useStartInvestigation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (alertId: string) => 
      api.post<Investigation>(`/v1/alerts/${alertId}/investigate`),
    
    onMutate: async (alertId) => {
      await queryClient.cancelQueries({ queryKey: alertKeys.all });
      
      const previousAlert = queryClient.getQueryData<Alert>(alertKeys.detail(alertId));
      
      // Optimistically update the alert to show investigation is starting
      if (previousAlert) {
        queryClient.setQueryData<Alert>(alertKeys.detail(alertId), {
          ...previousAlert,
          status: 'acknowledged',
        });
      }

      return { previousAlert };
    },
    
    onError: (_err, alertId, context) => {
      if (context?.previousAlert) {
        queryClient.setQueryData(alertKeys.detail(alertId), context.previousAlert);
      }
    },
    
    onSuccess: (investigation, alertId) => {
      // Update alert with investigation ID
      queryClient.setQueryData<Alert>(alertKeys.detail(alertId), (old) => 
        old ? { ...old, investigationId: investigation.id } : old
      );
      
      // Invalidate investigations to include new one
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}

// ==================== Combined Mutations Hook ====================

/**
 * Combined hook for all alert mutations
 * Convenient for components that need multiple alert actions
 */
export function useAlertMutations() {
  const acknowledge = useAcknowledgeAlert();
  const resolve = useResolveAlert();
  const silence = useSilenceAlert();
  const investigate = useStartInvestigation();

  return {
    acknowledge,
    resolve,
    silence,
    investigate,
    
    // Convenience methods that return promises
    acknowledgeAlert: acknowledge.mutateAsync,
    resolveAlert: resolve.mutateAsync,
    silenceAlert: silence.mutateAsync,
    startInvestigation: investigate.mutateAsync,
    
    // Loading states
    isLoading: 
      acknowledge.isPending || 
      resolve.isPending || 
      silence.isPending || 
      investigate.isPending,
  };
}
