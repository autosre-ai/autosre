/**
 * AutoSRE V2 - Alerts API Service
 * 
 * API service for managing alerts, silences, and acknowledgements.
 */

import api from './api';
import type { AxiosResponse } from 'axios';
import type {
  Alert,
  AlertFilter,
  AlertGroup,
  AlertSummary,
  AlertAcknowledgement,
  Silence,
  SilenceRequest,
  PaginatedResponse,
  ApiResponse,
} from '../types';

// Response types
export type AlertsListResponse = ApiResponse<PaginatedResponse<Alert>>;
export type AlertResponse = ApiResponse<Alert>;
export type AlertGroupsResponse = ApiResponse<AlertGroup[]>;
export type AlertSummaryResponse = ApiResponse<AlertSummary>;
export type SilencesListResponse = ApiResponse<Silence[]>;
export type SilenceResponse = ApiResponse<Silence>;

// Request types
export interface AcknowledgeAlertRequest {
  note?: string;
  duration?: number; // minutes
}

export interface ResolveAlertRequest {
  note?: string;
  rootCause?: string;
}

export interface BulkAlertActionRequest {
  alertIds: string[];
  note?: string;
}

export interface InvestigateAlertResponse {
  investigationId: string;
  status: 'created' | 'existing';
  message: string;
}

/**
 * Alerts API service
 */
export const alertsApi = {
  /**
   * List alerts with optional filtering
   */
  list: (
    params?: AlertFilter
  ): Promise<AxiosResponse<AlertsListResponse>> => {
    return api.get('/alerts', { params });
  },

  /**
   * Get a single alert by ID
   */
  get: (id: string): Promise<AxiosResponse<AlertResponse>> => {
    return api.get(`/alerts/${id}`);
  },

  /**
   * Get alert groups (similar to Alertmanager groups)
   */
  groups: (
    params?: Pick<AlertFilter, 'silenced' | 'inhibited'>
  ): Promise<AxiosResponse<AlertGroupsResponse>> => {
    return api.get('/alerts/groups', { params });
  },

  /**
   * Get alert summary statistics
   */
  summary: (
    params?: Pick<AlertFilter, 'service' | 'namespace' | 'cluster'>
  ): Promise<AxiosResponse<AlertSummaryResponse>> => {
    return api.get('/alerts/summary', { params });
  },

  /**
   * Start an investigation for an alert
   */
  investigate: (
    id: string
  ): Promise<AxiosResponse<ApiResponse<InvestigateAlertResponse>>> => {
    return api.post(`/alerts/${id}/investigate`);
  },

  /**
   * Acknowledge an alert
   */
  acknowledge: (
    id: string,
    data?: AcknowledgeAlertRequest
  ): Promise<AxiosResponse<ApiResponse<AlertAcknowledgement>>> => {
    return api.post(`/alerts/${id}/acknowledge`, data);
  },

  /**
   * Resolve an alert
   */
  resolve: (
    id: string,
    data?: ResolveAlertRequest
  ): Promise<AxiosResponse<AlertResponse>> => {
    return api.post(`/alerts/${id}/resolve`, data);
  },

  /**
   * Unacknowledge an alert
   */
  unacknowledge: (id: string): Promise<AxiosResponse<AlertResponse>> => {
    return api.post(`/alerts/${id}/unacknowledge`);
  },

  /**
   * Bulk acknowledge alerts
   */
  bulkAcknowledge: (
    data: BulkAlertActionRequest
  ): Promise<AxiosResponse<ApiResponse<{ acknowledged: number }>>> => {
    return api.post('/alerts/bulk/acknowledge', data);
  },

  /**
   * Bulk resolve alerts
   */
  bulkResolve: (
    data: BulkAlertActionRequest
  ): Promise<AxiosResponse<ApiResponse<{ resolved: number }>>> => {
    return api.post('/alerts/bulk/resolve', data);
  },

  /**
   * Get alert history/timeline
   */
  history: (
    id: string,
    params?: { limit?: number; offset?: number }
  ): Promise<
    AxiosResponse<
      ApiResponse<
        Array<{
          timestamp: string;
          action: string;
          actor?: string;
          details?: Record<string, unknown>;
        }>
      >
    >
  > => {
    return api.get(`/alerts/${id}/history`, { params });
  },

  /**
   * Get related alerts
   */
  related: (
    id: string,
    params?: { limit?: number }
  ): Promise<AxiosResponse<ApiResponse<Alert[]>>> => {
    return api.get(`/alerts/${id}/related`, { params });
  },

  // Silence management

  /**
   * List all silences
   */
  listSilences: (params?: {
    state?: 'active' | 'pending' | 'expired';
  }): Promise<AxiosResponse<SilencesListResponse>> => {
    return api.get('/alerts/silences', { params });
  },

  /**
   * Create a new silence
   */
  createSilence: (
    data: SilenceRequest
  ): Promise<AxiosResponse<SilenceResponse>> => {
    return api.post('/alerts/silences', data);
  },

  /**
   * Get a silence by ID
   */
  getSilence: (id: string): Promise<AxiosResponse<SilenceResponse>> => {
    return api.get(`/alerts/silences/${id}`);
  },

  /**
   * Update a silence
   */
  updateSilence: (
    id: string,
    data: Partial<SilenceRequest>
  ): Promise<AxiosResponse<SilenceResponse>> => {
    return api.put(`/alerts/silences/${id}`, data);
  },

  /**
   * Delete/expire a silence
   */
  deleteSilence: (id: string): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/alerts/silences/${id}`);
  },

  /**
   * Create a silence for a specific alert
   */
  silenceAlert: (
    id: string,
    data: {
      duration: number; // minutes
      comment: string;
    }
  ): Promise<AxiosResponse<SilenceResponse>> => {
    return api.post(`/alerts/${id}/silence`, data);
  },
};

export default alertsApi;
