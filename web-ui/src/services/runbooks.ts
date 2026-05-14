/**
 * AutoSRE V2 - Runbooks API Service
 * 
 * API service for managing runbooks and their executions.
 */

import api from './api';
import type { AxiosResponse } from 'axios';
import type {
  Runbook,
  RunbookFilter,
  RunbookExecution,
  RunbookExecutionFilter,
  RunbookSummary,
  CreateRunbookRequest,
  UpdateRunbookRequest,
  ExecuteRunbookRequest,
  RunbookStep,
  RunbookStepExecution,
  PaginatedResponse,
  ApiResponse,
} from '../types';

// Response types
export type RunbooksListResponse = ApiResponse<PaginatedResponse<Runbook>>;
export type RunbookResponse = ApiResponse<Runbook>;
export type RunbookExecutionsListResponse = ApiResponse<PaginatedResponse<RunbookExecution>>;
export type RunbookExecutionResponse = ApiResponse<RunbookExecution>;
export type RunbookSummaryResponse = ApiResponse<RunbookSummary>;

// Request types
export interface ValidateRunbookRequest {
  steps: Omit<RunbookStep, 'id'>[];
  variables?: Runbook['variables'];
}

export interface ValidateRunbookResponse {
  valid: boolean;
  errors: Array<{
    stepIndex: number;
    field: string;
    message: string;
  }>;
  warnings: Array<{
    stepIndex: number;
    message: string;
  }>;
}

export interface ApproveStepRequest {
  comment?: string;
}

export interface CloneRunbookRequest {
  name?: string;
  includeDraft?: boolean;
}

export interface RunbookVersionInfo {
  version: number;
  createdAt: string;
  createdBy: string;
  changes: string;
}

/**
 * Runbooks API service
 */
export const runbooksApi = {
  // Runbook management

  /**
   * List runbooks with optional filtering
   */
  list: (
    params?: RunbookFilter
  ): Promise<AxiosResponse<RunbooksListResponse>> => {
    return api.get('/runbooks', { params });
  },

  /**
   * Get a single runbook by ID
   */
  get: (id: string): Promise<AxiosResponse<RunbookResponse>> => {
    return api.get(`/runbooks/${id}`);
  },

  /**
   * Get a specific version of a runbook
   */
  getVersion: (
    id: string,
    version: number
  ): Promise<AxiosResponse<RunbookResponse>> => {
    return api.get(`/runbooks/${id}/versions/${version}`);
  },

  /**
   * List all versions of a runbook
   */
  listVersions: (
    id: string
  ): Promise<AxiosResponse<ApiResponse<RunbookVersionInfo[]>>> => {
    return api.get(`/runbooks/${id}/versions`);
  },

  /**
   * Create a new runbook
   */
  create: (
    data: CreateRunbookRequest
  ): Promise<AxiosResponse<RunbookResponse>> => {
    return api.post('/runbooks', data);
  },

  /**
   * Update a runbook
   */
  update: (
    id: string,
    data: UpdateRunbookRequest
  ): Promise<AxiosResponse<RunbookResponse>> => {
    return api.patch(`/runbooks/${id}`, data);
  },

  /**
   * Delete a runbook
   */
  delete: (id: string): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/runbooks/${id}`);
  },

  /**
   * Clone a runbook
   */
  clone: (
    id: string,
    data?: CloneRunbookRequest
  ): Promise<AxiosResponse<RunbookResponse>> => {
    return api.post(`/runbooks/${id}/clone`, data);
  },

  /**
   * Publish a runbook (draft -> published)
   */
  publish: (id: string): Promise<AxiosResponse<RunbookResponse>> => {
    return api.post(`/runbooks/${id}/publish`);
  },

  /**
   * Deprecate a runbook
   */
  deprecate: (
    id: string,
    reason?: string
  ): Promise<AxiosResponse<RunbookResponse>> => {
    return api.post(`/runbooks/${id}/deprecate`, { reason });
  },

  /**
   * Archive a runbook
   */
  archive: (id: string): Promise<AxiosResponse<RunbookResponse>> => {
    return api.post(`/runbooks/${id}/archive`);
  },

  /**
   * Validate runbook steps
   */
  validate: (
    data: ValidateRunbookRequest
  ): Promise<AxiosResponse<ApiResponse<ValidateRunbookResponse>>> => {
    return api.post('/runbooks/validate', data);
  },

  /**
   * Get runbook summary statistics
   */
  summary: (params?: {
    timeRange?: string;
  }): Promise<AxiosResponse<RunbookSummaryResponse>> => {
    return api.get('/runbooks/summary', { params });
  },

  /**
   * Get runbook categories
   */
  categories: (): Promise<AxiosResponse<ApiResponse<string[]>>> => {
    return api.get('/runbooks/categories');
  },

  // Execution management

  /**
   * List runbook executions
   */
  listExecutions: (
    params?: RunbookExecutionFilter
  ): Promise<AxiosResponse<RunbookExecutionsListResponse>> => {
    return api.get('/runbooks/executions', { params });
  },

  /**
   * Get a single execution by ID
   */
  getExecution: (
    executionId: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.get(`/runbooks/executions/${executionId}`);
  },

  /**
   * Execute a runbook
   */
  execute: (
    data: ExecuteRunbookRequest
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post('/runbooks/execute', data);
  },

  /**
   * Execute a runbook for a specific alert
   */
  executeForAlert: (
    runbookId: string,
    alertId: string,
    variables?: Record<string, unknown>
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post('/runbooks/execute', {
      runbookId,
      alertId,
      variables,
    });
  },

  /**
   * Execute a runbook for an investigation
   */
  executeForInvestigation: (
    runbookId: string,
    investigationId: string,
    variables?: Record<string, unknown>
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post('/runbooks/execute', {
      runbookId,
      investigationId,
      variables,
    });
  },

  /**
   * Pause a running execution
   */
  pauseExecution: (
    executionId: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(`/runbooks/executions/${executionId}/pause`);
  },

  /**
   * Resume a paused execution
   */
  resumeExecution: (
    executionId: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(`/runbooks/executions/${executionId}/resume`);
  },

  /**
   * Cancel an execution
   */
  cancelExecution: (
    executionId: string,
    reason?: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(`/runbooks/executions/${executionId}/cancel`, { reason });
  },

  /**
   * Retry a failed execution
   */
  retryExecution: (
    executionId: string,
    fromStep?: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(`/runbooks/executions/${executionId}/retry`, { fromStep });
  },

  // Step-level operations

  /**
   * Approve a step waiting for approval
   */
  approveStep: (
    executionId: string,
    stepId: string,
    data?: ApproveStepRequest
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(
      `/runbooks/executions/${executionId}/steps/${stepId}/approve`,
      data
    );
  },

  /**
   * Reject a step waiting for approval
   */
  rejectStep: (
    executionId: string,
    stepId: string,
    reason: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(
      `/runbooks/executions/${executionId}/steps/${stepId}/reject`,
      { reason }
    );
  },

  /**
   * Skip a step
   */
  skipStep: (
    executionId: string,
    stepId: string,
    reason: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(
      `/runbooks/executions/${executionId}/steps/${stepId}/skip`,
      { reason }
    );
  },

  /**
   * Retry a failed step
   */
  retryStep: (
    executionId: string,
    stepId: string
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(
      `/runbooks/executions/${executionId}/steps/${stepId}/retry`
    );
  },

  /**
   * Submit manual step input
   */
  submitStepInput: (
    executionId: string,
    stepId: string,
    inputs: Record<string, unknown>
  ): Promise<AxiosResponse<RunbookExecutionResponse>> => {
    return api.post(
      `/runbooks/executions/${executionId}/steps/${stepId}/input`,
      { inputs }
    );
  },

  /**
   * Get step logs
   */
  getStepLogs: (
    executionId: string,
    stepId: string
  ): Promise<AxiosResponse<ApiResponse<RunbookStepExecution['logs']>>> => {
    return api.get(
      `/runbooks/executions/${executionId}/steps/${stepId}/logs`
    );
  },

  // Search and recommendations

  /**
   * Search runbooks
   */
  search: (
    query: string,
    params?: { limit?: number; category?: string }
  ): Promise<AxiosResponse<ApiResponse<Runbook[]>>> => {
    return api.get('/runbooks/search', { params: { query, ...params } });
  },

  /**
   * Get recommended runbooks for an alert
   */
  getRecommendations: (
    alertId: string,
    params?: { limit?: number }
  ): Promise<
    AxiosResponse<
      ApiResponse<
        Array<{
          runbook: Runbook;
          confidence: number;
          reason: string;
        }>
      >
    >
  > => {
    return api.get(`/runbooks/recommendations/${alertId}`, { params });
  },

  /**
   * Get runbooks matching alert labels
   */
  matchForAlert: (
    alertId: string
  ): Promise<AxiosResponse<ApiResponse<Runbook[]>>> => {
    return api.get(`/runbooks/match/${alertId}`);
  },

  // Import/Export

  /**
   * Export a runbook
   */
  export: (
    id: string,
    format: 'yaml' | 'json'
  ): Promise<AxiosResponse<Blob>> => {
    return api.get(`/runbooks/${id}/export`, {
      params: { format },
      responseType: 'blob',
    });
  },

  /**
   * Import a runbook
   */
  import: (
    file: File,
    options?: { overwrite?: boolean }
  ): Promise<AxiosResponse<RunbookResponse>> => {
    const formData = new FormData();
    formData.append('file', file);
    if (options?.overwrite) {
      formData.append('overwrite', 'true');
    }
    return api.post('/runbooks/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  /**
   * Export execution report
   */
  exportExecution: (
    executionId: string,
    format: 'pdf' | 'markdown' | 'json'
  ): Promise<AxiosResponse<Blob>> => {
    return api.get(`/runbooks/executions/${executionId}/export`, {
      params: { format },
      responseType: 'blob',
    });
  },
};

export default runbooksApi;
