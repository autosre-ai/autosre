import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Alert, Investigation, ChatSession, Runbook, RunbookExecution, Integration, DashboardMetrics, SystemHealth } from '@/types';

// ==================== Dashboard Hooks ====================
export function useDashboardMetrics() {
  return useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: () => api.get<DashboardMetrics>('/v1/dashboard/metrics'),
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ['dashboard', 'health'],
    queryFn: () => api.get<SystemHealth>('/v1/dashboard/health'),
    refetchInterval: 15000,
  });
}

// ==================== Alert Hooks ====================
export function useAlerts(filters?: { severity?: string; status?: string; service?: string }) {
  return useQuery({
    queryKey: ['alerts', filters],
    queryFn: () => api.get<Alert[]>('/v1/alerts', filters as Record<string, string>),
    refetchInterval: 10000,
  });
}

export function useAlert(id: string) {
  return useQuery({
    queryKey: ['alerts', id],
    queryFn: () => api.get<Alert>(`/v1/alerts/${id}`),
    enabled: !!id,
  });
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.post(`/v1/alerts/${id}/acknowledge`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useResolveAlert() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.post(`/v1/alerts/${id}/resolve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useSilenceAlert() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, duration }: { id: string; duration: number }) =>
      api.post(`/v1/alerts/${id}/silence`, { duration }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useInvestigateAlert() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.post<Investigation>(`/v1/alerts/${id}/investigate`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}

// ==================== Investigation Hooks ====================
export function useInvestigations(filters?: { status?: string; severity?: string }) {
  return useQuery({
    queryKey: ['investigations', filters],
    queryFn: () => api.get<Investigation[]>('/v1/investigations', filters as Record<string, string>),
    refetchInterval: 5000,
  });
}

export function useInvestigation(id: string) {
  return useQuery({
    queryKey: ['investigations', id],
    queryFn: () => api.get<Investigation>(`/v1/investigations/${id}`),
    enabled: !!id,
    refetchInterval: 3000, // More frequent updates for active investigations
  });
}

export function useApproveAction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ investigationId, stepId }: { investigationId: string; stepId: string }) =>
      api.post(`/v1/investigations/${investigationId}/steps/${stepId}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}

export function useRejectAction() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ investigationId, stepId, reason }: { investigationId: string; stepId: string; reason?: string }) =>
      api.post(`/v1/investigations/${investigationId}/steps/${stepId}/reject`, { reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['investigations'] });
    },
  });
}

// ==================== Chat Hooks ====================
export function useChatSessions() {
  return useQuery({
    queryKey: ['chat', 'sessions'],
    queryFn: () => api.get<ChatSession[]>('/v1/chat/sessions'),
  });
}

export function useChatSession(id: string) {
  return useQuery({
    queryKey: ['chat', 'sessions', id],
    queryFn: () => api.get<ChatSession>(`/v1/chat/sessions/${id}`),
    enabled: !!id,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (params?: { investigationId?: string }) =>
      api.post<ChatSession>('/v1/chat/sessions', params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] });
    },
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ sessionId, message }: { sessionId: string; message: string }) =>
      api.post(`/v1/chat/sessions/${sessionId}/messages`, { content: message }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions', variables.sessionId] });
    },
  });
}

// ==================== Runbook Hooks ====================
export function useRunbooks(filters?: { category?: string; status?: string }) {
  return useQuery({
    queryKey: ['runbooks', filters],
    queryFn: () => api.get<Runbook[]>('/v1/runbooks', filters as Record<string, string>),
  });
}

export function useRunbook(id: string) {
  return useQuery({
    queryKey: ['runbooks', id],
    queryFn: () => api.get<Runbook>(`/v1/runbooks/${id}`),
    enabled: !!id,
  });
}

export function useCreateRunbook() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (runbook: Partial<Runbook>) => api.post<Runbook>('/v1/runbooks', runbook),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbooks'] });
    },
  });
}

export function useUpdateRunbook() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Runbook> & { id: string }) =>
      api.put<Runbook>(`/v1/runbooks/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbooks'] });
    },
  });
}

export function useDeleteRunbook() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.delete(`/v1/runbooks/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbooks'] });
    },
  });
}

export function useExecuteRunbook() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, alertId }: { id: string; alertId?: string }) =>
      api.post<RunbookExecution>(`/v1/runbooks/${id}/execute`, { alertId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runbook-executions'] });
    },
  });
}

export function useRunbookExecutions(runbookId?: string) {
  return useQuery({
    queryKey: ['runbook-executions', runbookId],
    queryFn: () =>
      api.get<RunbookExecution[]>(
        runbookId ? `/v1/runbooks/${runbookId}/executions` : '/v1/runbook-executions'
      ),
  });
}

// ==================== Settings Hooks ====================
export function useIntegrations() {
  return useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.get<Integration[]>('/v1/integrations'),
  });
}

export function useConnectIntegration() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, config }: { id: string; config: Record<string, string> }) =>
      api.post(`/v1/integrations/${id}/connect`, { config }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] });
    },
  });
}

export function useDisconnectIntegration() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => api.post(`/v1/integrations/${id}/disconnect`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integrations'] });
    },
  });
}
