import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Runbook, RunbookExecution, RunbookStatus, ExecutionStatus, RiskLevel } from '@/types';

// ==================== Types ====================
export interface RunbookFilters {
  category?: string;
  status?: RunbookStatus;
  tags?: string[];
  search?: string;
}

export interface CreateRunbookParams {
  name: string;
  description: string;
  category: string;
  tags?: string[];
  steps: Runbook['steps'];
}

export interface UpdateRunbookParams extends Partial<CreateRunbookParams> {
  id: string;
  status?: RunbookStatus;
}

export interface ExecuteRunbookParams {
  id: string;
  alertId?: string;
  parameters?: Record<string, string>;
}

// ==================== Query Keys ====================
export const runbookKeys = {
  all: ['runbooks'] as const,
  lists: () => [...runbookKeys.all, 'list'] as const,
  list: (filters?: RunbookFilters) => [...runbookKeys.lists(), filters] as const,
  details: () => [...runbookKeys.all, 'detail'] as const,
  detail: (id: string) => [...runbookKeys.details(), id] as const,
  executions: () => ['runbook-executions'] as const,
  executionsList: (runbookId?: string) => [...runbookKeys.executions(), 'list', runbookId] as const,
  execution: (id: string) => [...runbookKeys.executions(), 'detail', id] as const,
  categories: () => [...runbookKeys.all, 'categories'] as const,
};

// ==================== Queries ====================

/**
 * Fetch all runbooks with optional filters
 */
export function useRunbooks(filters?: RunbookFilters) {
  return useQuery({
    queryKey: runbookKeys.list(filters),
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (filters?.category) params.category = filters.category;
      if (filters?.status) params.status = filters.status;
      if (filters?.tags?.length) params.tags = filters.tags.join(',');
      if (filters?.search) params.search = filters.search;
      
      return api.get<Runbook[]>('/v1/runbooks', Object.keys(params).length > 0 ? params : undefined);
    },
    staleTime: 30000,
  });
}

/**
 * Fetch a single runbook by ID
 */
export function useRunbook(id: string) {
  return useQuery({
    queryKey: runbookKeys.detail(id),
    queryFn: () => api.get<Runbook>(`/v1/runbooks/${id}`),
    enabled: !!id,
    staleTime: 30000,
  });
}

/**
 * Fetch runbook categories
 */
export function useRunbookCategories() {
  return useQuery({
    queryKey: runbookKeys.categories(),
    queryFn: () => api.get<string[]>('/v1/runbooks/categories'),
    staleTime: 60000,
  });
}

/**
 * Fetch runbook executions
 */
export function useRunbookExecutions(runbookId?: string) {
  return useQuery({
    queryKey: runbookKeys.executionsList(runbookId),
    queryFn: () =>
      api.get<RunbookExecution[]>(
        runbookId ? `/v1/runbooks/${runbookId}/executions` : '/v1/runbook-executions'
      ),
    refetchInterval: (query) => {
      // Poll if any execution is running
      const data = query.state.data;
      if (data?.some((e: RunbookExecution) => e.status === 'running')) {
        return 3000;
      }
      return false;
    },
  });
}

/**
 * Fetch a single runbook execution
 */
export function useRunbookExecution(id: string) {
  return useQuery({
    queryKey: runbookKeys.execution(id),
    queryFn: () => api.get<RunbookExecution>(`/v1/runbook-executions/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'running') {
        return 2000;
      }
      return false;
    },
  });
}

// ==================== Mutations ====================

/**
 * Create a new runbook
 */
export function useCreateRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: CreateRunbookParams) =>
      api.post<Runbook>('/v1/runbooks', params),
    
    onSuccess: (newRunbook) => {
      // Add to list cache
      queryClient.setQueryData<Runbook[]>(
        runbookKeys.lists(),
        (old) => old ? [newRunbook, ...old] : [newRunbook]
      );
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.lists() });
      queryClient.invalidateQueries({ queryKey: runbookKeys.categories() });
    },
  });
}

/**
 * Update an existing runbook
 * Supports partial updates
 */
export function useUpdateRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ...data }: UpdateRunbookParams) =>
      api.put<Runbook>(`/v1/runbooks/${id}`, data),
    
    onMutate: async ({ id, ...data }) => {
      await queryClient.cancelQueries({ queryKey: runbookKeys.detail(id) });
      
      const previousRunbook = queryClient.getQueryData<Runbook>(runbookKeys.detail(id));
      
      if (previousRunbook) {
        queryClient.setQueryData<Runbook>(runbookKeys.detail(id), {
          ...previousRunbook,
          ...data,
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousRunbook };
    },
    
    onError: (_err, { id }, context) => {
      if (context?.previousRunbook) {
        queryClient.setQueryData(runbookKeys.detail(id), context.previousRunbook);
      }
    },
    
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: runbookKeys.lists() });
    },
  });
}

/**
 * Delete a runbook
 */
export function useDeleteRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/v1/runbooks/${id}`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: runbookKeys.lists() });
      
      const previousRunbooks = queryClient.getQueryData<Runbook[]>(runbookKeys.lists());
      
      // Optimistically remove from list
      queryClient.setQueriesData<Runbook[]>(
        { queryKey: runbookKeys.lists() },
        (old) => old?.filter(r => r.id !== id)
      );

      return { previousRunbooks };
    },
    
    onError: (_err, _id, context) => {
      if (context?.previousRunbooks) {
        queryClient.setQueryData(runbookKeys.lists(), context.previousRunbooks);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.all });
    },
  });
}

/**
 * Activate a draft runbook
 */
export function usePublishRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      api.post<Runbook>(`/v1/runbooks/${id}/activate`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: runbookKeys.detail(id) });
      
      const previousRunbook = queryClient.getQueryData<Runbook>(runbookKeys.detail(id));
      
      if (previousRunbook) {
        queryClient.setQueryData<Runbook>(runbookKeys.detail(id), {
          ...previousRunbook,
          status: 'active' as RunbookStatus,
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousRunbook };
    },
    
    onError: (_err, id, context) => {
      if (context?.previousRunbook) {
        queryClient.setQueryData(runbookKeys.detail(id), context.previousRunbook);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.all });
    },
  });
}

/**
 * Archive a runbook
 */
export function useArchiveRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      api.post<Runbook>(`/v1/runbooks/${id}/archive`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: runbookKeys.detail(id) });
      
      const previousRunbook = queryClient.getQueryData<Runbook>(runbookKeys.detail(id));
      
      if (previousRunbook) {
        queryClient.setQueryData<Runbook>(runbookKeys.detail(id), {
          ...previousRunbook,
          status: 'archived',
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousRunbook };
    },
    
    onError: (_err, id, context) => {
      if (context?.previousRunbook) {
        queryClient.setQueryData(runbookKeys.detail(id), context.previousRunbook);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.all });
    },
  });
}

/**
 * Duplicate a runbook
 */
export function useDuplicateRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) =>
      api.post<Runbook>(`/v1/runbooks/${id}/duplicate`),
    
    onSuccess: (newRunbook) => {
      queryClient.setQueryData<Runbook[]>(
        runbookKeys.lists(),
        (old) => old ? [newRunbook, ...old] : [newRunbook]
      );
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.lists() });
    },
  });
}

/**
 * Execute a runbook
 * Returns the execution object for tracking progress
 */
export function useExecuteRunbook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, alertId, parameters }: ExecuteRunbookParams) =>
      api.post<RunbookExecution>(`/v1/runbooks/${id}/execute`, { alertId, parameters }),
    
    onSuccess: (execution, { id }) => {
      // Add to executions list
      queryClient.setQueryData<RunbookExecution[]>(
        runbookKeys.executionsList(id),
        (old) => old ? [execution, ...old] : [execution]
      );
    },
    
    onSettled: (_data, _err, { id }) => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: runbookKeys.executions() });
    },
  });
}

/**
 * Cancel a running execution
 */
export function useCancelExecution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (executionId: string) =>
      api.post(`/v1/runbook-executions/${executionId}/cancel`),
    
    onMutate: async (executionId) => {
      await queryClient.cancelQueries({ queryKey: runbookKeys.execution(executionId) });
      
      const previousExecution = queryClient.getQueryData<RunbookExecution>(
        runbookKeys.execution(executionId)
      );
      
      if (previousExecution) {
        queryClient.setQueryData<RunbookExecution>(
          runbookKeys.execution(executionId),
          {
            ...previousExecution,
            status: 'cancelled' as ExecutionStatus,
            completedAt: new Date().toISOString(),
          }
        );
      }

      return { previousExecution };
    },
    
    onError: (_err, executionId, context) => {
      if (context?.previousExecution) {
        queryClient.setQueryData(runbookKeys.execution(executionId), context.previousExecution);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.executions() });
    },
  });
}

/**
 * Approve a step in a runbook execution
 */
export function useApproveExecutionStep() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ executionId, stepId }: { executionId: string; stepId: string }) =>
      api.post(`/v1/runbook-executions/${executionId}/steps/${stepId}/approve`),
    
    onSettled: (_data, _err, { executionId }) => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.execution(executionId) });
    },
  });
}

/**
 * Skip a step in a runbook execution
 */
export function useSkipExecutionStep() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ executionId, stepId, reason }: { executionId: string; stepId: string; reason?: string }) =>
      api.post(`/v1/runbook-executions/${executionId}/steps/${stepId}/skip`, { reason }),
    
    onSettled: (_data, _err, { executionId }) => {
      queryClient.invalidateQueries({ queryKey: runbookKeys.execution(executionId) });
    },
  });
}
