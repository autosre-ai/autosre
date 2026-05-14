/**
 * AutoSRE V2 - Investigations API Service
 * 
 * API service for managing AI-driven incident investigations.
 */

import api from './api';
import type { AxiosResponse } from 'axios';
import type {
  Investigation,
  InvestigationFilter,
  InvestigationSummary,
  CreateInvestigationRequest,
  UpdateInvestigationRequest,
  Observation,
  Hypothesis,
  Finding,
  PaginatedResponse,
  ApiResponse,
} from '../types';

// Response types
export type InvestigationsListResponse = ApiResponse<PaginatedResponse<Investigation>>;
export type InvestigationResponse = ApiResponse<Investigation>;
export type InvestigationSummaryResponse = ApiResponse<InvestigationSummary>;
export type ObservationsResponse = ApiResponse<Observation[]>;
export type HypothesesResponse = ApiResponse<Hypothesis[]>;
export type FindingsResponse = ApiResponse<Finding[]>;

// Request types
export interface AddObservationRequest {
  type: Observation['type'];
  source: string;
  data: Record<string, unknown>;
  summary: string;
  metadata?: Observation['metadata'];
}

export interface CreateHypothesisRequest {
  title: string;
  description: string;
  testPlan?: string;
  supportingObservations?: string[];
}

export interface UpdateHypothesisRequest {
  status?: Hypothesis['status'];
  confidence?: number;
  testResults?: string;
  supportingObservations?: string[];
  contradictingObservations?: string[];
}

export interface CreateFindingRequest {
  type: Finding['type'];
  severity: Finding['severity'];
  title: string;
  description: string;
  evidence: string[];
  affectedComponents: string[];
  recommendations?: string[];
  relatedHypotheses?: string[];
}

export interface RunAnalysisRequest {
  analysisType: 'metrics' | 'logs' | 'traces' | 'full' | 'custom';
  timeRange?: {
    start: string;
    end: string;
  };
  options?: {
    services?: string[];
    depth?: 'shallow' | 'normal' | 'deep';
    includeCorrelations?: boolean;
  };
}

export interface InvestigationActionResponse {
  success: boolean;
  message: string;
  stepId?: string;
}

/**
 * Investigations API service
 */
export const investigationsApi = {
  /**
   * List investigations with optional filtering
   */
  list: (
    params?: InvestigationFilter
  ): Promise<AxiosResponse<InvestigationsListResponse>> => {
    return api.get('/investigations', { params });
  },

  /**
   * Get a single investigation by ID
   */
  get: (id: string): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.get(`/investigations/${id}`);
  },

  /**
   * Create a new investigation
   */
  create: (
    data: CreateInvestigationRequest
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.post('/investigations', data);
  },

  /**
   * Update an investigation
   */
  update: (
    id: string,
    data: UpdateInvestigationRequest
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.patch(`/investigations/${id}`, data);
  },

  /**
   * Delete an investigation
   */
  delete: (id: string): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/investigations/${id}`);
  },

  /**
   * Get investigation summary statistics
   */
  summary: (params?: {
    timeRange?: string;
  }): Promise<AxiosResponse<InvestigationSummaryResponse>> => {
    return api.get('/investigations/summary', { params });
  },

  // Investigation lifecycle actions

  /**
   * Start an investigation (trigger AI analysis)
   */
  start: (
    id: string
  ): Promise<AxiosResponse<ApiResponse<InvestigationActionResponse>>> => {
    return api.post(`/investigations/${id}/start`);
  },

  /**
   * Pause a running investigation
   */
  pause: (
    id: string
  ): Promise<AxiosResponse<ApiResponse<InvestigationActionResponse>>> => {
    return api.post(`/investigations/${id}/pause`);
  },

  /**
   * Resume a paused investigation
   */
  resume: (
    id: string
  ): Promise<AxiosResponse<ApiResponse<InvestigationActionResponse>>> => {
    return api.post(`/investigations/${id}/resume`);
  },

  /**
   * Complete an investigation
   */
  complete: (
    id: string,
    data?: { summary?: string; rootCauseId?: string }
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.post(`/investigations/${id}/complete`, data);
  },

  /**
   * Cancel an investigation
   */
  cancel: (
    id: string,
    data?: { reason?: string }
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.post(`/investigations/${id}/cancel`, data);
  },

  /**
   * Run a specific analysis type
   */
  runAnalysis: (
    id: string,
    data: RunAnalysisRequest
  ): Promise<AxiosResponse<ApiResponse<InvestigationActionResponse>>> => {
    return api.post(`/investigations/${id}/analyze`, data);
  },

  // Observations management

  /**
   * Get all observations for an investigation
   */
  getObservations: (
    id: string,
    params?: { type?: Observation['type']; limit?: number }
  ): Promise<AxiosResponse<ObservationsResponse>> => {
    return api.get(`/investigations/${id}/observations`, { params });
  },

  /**
   * Add an observation to an investigation
   */
  addObservation: (
    id: string,
    data: AddObservationRequest
  ): Promise<AxiosResponse<ApiResponse<Observation>>> => {
    return api.post(`/investigations/${id}/observations`, data);
  },

  /**
   * Delete an observation
   */
  deleteObservation: (
    id: string,
    observationId: string
  ): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/investigations/${id}/observations/${observationId}`);
  },

  // Hypotheses management

  /**
   * Get all hypotheses for an investigation
   */
  getHypotheses: (
    id: string,
    params?: { status?: Hypothesis['status'] }
  ): Promise<AxiosResponse<HypothesesResponse>> => {
    return api.get(`/investigations/${id}/hypotheses`, { params });
  },

  /**
   * Create a new hypothesis
   */
  createHypothesis: (
    id: string,
    data: CreateHypothesisRequest
  ): Promise<AxiosResponse<ApiResponse<Hypothesis>>> => {
    return api.post(`/investigations/${id}/hypotheses`, data);
  },

  /**
   * Update a hypothesis
   */
  updateHypothesis: (
    id: string,
    hypothesisId: string,
    data: UpdateHypothesisRequest
  ): Promise<AxiosResponse<ApiResponse<Hypothesis>>> => {
    return api.patch(`/investigations/${id}/hypotheses/${hypothesisId}`, data);
  },

  /**
   * Delete a hypothesis
   */
  deleteHypothesis: (
    id: string,
    hypothesisId: string
  ): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/investigations/${id}/hypotheses/${hypothesisId}`);
  },

  // Findings management

  /**
   * Get all findings for an investigation
   */
  getFindings: (
    id: string,
    params?: { type?: Finding['type']; severity?: Finding['severity'] }
  ): Promise<AxiosResponse<FindingsResponse>> => {
    return api.get(`/investigations/${id}/findings`, { params });
  },

  /**
   * Create a new finding
   */
  createFinding: (
    id: string,
    data: CreateFindingRequest
  ): Promise<AxiosResponse<ApiResponse<Finding>>> => {
    return api.post(`/investigations/${id}/findings`, data);
  },

  /**
   * Update a finding
   */
  updateFinding: (
    id: string,
    findingId: string,
    data: Partial<CreateFindingRequest>
  ): Promise<AxiosResponse<ApiResponse<Finding>>> => {
    return api.patch(`/investigations/${id}/findings/${findingId}`, data);
  },

  /**
   * Delete a finding
   */
  deleteFinding: (
    id: string,
    findingId: string
  ): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/investigations/${id}/findings/${findingId}`);
  },

  /**
   * Set the root cause finding
   */
  setRootCause: (
    id: string,
    findingId: string
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.post(`/investigations/${id}/root-cause`, { findingId });
  },

  // Timeline and history

  /**
   * Get the investigation timeline
   */
  getTimeline: (
    id: string,
    params?: { limit?: number; offset?: number }
  ): Promise<AxiosResponse<ApiResponse<Investigation['timeline']>>> => {
    return api.get(`/investigations/${id}/timeline`, { params });
  },

  // Related items

  /**
   * Add alerts to an investigation
   */
  addAlerts: (
    id: string,
    alertIds: string[]
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.post(`/investigations/${id}/alerts`, { alertIds });
  },

  /**
   * Remove an alert from an investigation
   */
  removeAlert: (
    id: string,
    alertId: string
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.delete(`/investigations/${id}/alerts/${alertId}`);
  },

  /**
   * Link related investigations
   */
  linkInvestigation: (
    id: string,
    relatedId: string
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.post(`/investigations/${id}/related`, { relatedId });
  },

  /**
   * Unlink related investigations
   */
  unlinkInvestigation: (
    id: string,
    relatedId: string
  ): Promise<AxiosResponse<InvestigationResponse>> => {
    return api.delete(`/investigations/${id}/related/${relatedId}`);
  },

  // Export

  /**
   * Export investigation report
   */
  export: (
    id: string,
    format: 'pdf' | 'markdown' | 'json'
  ): Promise<AxiosResponse<Blob>> => {
    return api.get(`/investigations/${id}/export`, {
      params: { format },
      responseType: 'blob',
    });
  },
};

export default investigationsApi;
