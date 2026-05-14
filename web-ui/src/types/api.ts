/**
 * API Types for AutoSRE V2
 */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  field?: string;
  timestamp: string;
  requestId?: string;
  path?: string;
  stack?: string;
}

export interface ApiValidationError extends ApiError {
  code: 'VALIDATION_ERROR';
  errors: Array<{
    field: string;
    message: string;
    code: string;
    value?: unknown;
  }>;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta?: {
    requestId: string;
    timestamp: string;
    duration?: number;
  };
}

export interface ApiListResponse<T> extends ApiResponse<PaginatedResponse<T>> {
  data: PaginatedResponse<T>;
}

export interface ApiSingleResponse<T> extends ApiResponse<T> {
  data: T;
}

export interface ApiEmptyResponse extends ApiResponse<void> {
  success: true;
  data?: undefined;
}

export interface ApiErrorResponse extends ApiResponse<never> {
  success: false;
  error: ApiError;
  data?: undefined;
}

export type ApiResult<T> = ApiSingleResponse<T> | ApiErrorResponse;
export type ApiListResult<T> = ApiListResponse<T> | ApiErrorResponse;

export interface PaginationParams {
  page?: number;
  pageSize?: number;
  limit?: number;
  offset?: number;
}

export interface SortParams {
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface SearchParams {
  search?: string;
  query?: string;
}

export type ListParams = PaginationParams & SortParams & SearchParams;

export interface BatchRequest<T> {
  items: T[];
  continueOnError?: boolean;
}

export interface BatchResponse<T> {
  results: Array<{
    success: boolean;
    data?: T;
    error?: ApiError;
    index: number;
  }>;
  totalSuccess: number;
  totalFailed: number;
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime: number;
  timestamp: string;
  checks: Record<
    string,
    {
      status: 'healthy' | 'degraded' | 'unhealthy';
      latency?: number;
      message?: string;
      lastChecked: string;
    }
  >;
}

export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;
  id: string;
}

export interface WebSocketSubscription {
  channel: string;
  filters?: Record<string, unknown>;
}

export enum WebSocketEventType {
  ALERT_CREATED = 'alert:created',
  ALERT_UPDATED = 'alert:updated',
  ALERT_RESOLVED = 'alert:resolved',
  INVESTIGATION_STARTED = 'investigation:started',
  INVESTIGATION_UPDATED = 'investigation:updated',
  INVESTIGATION_COMPLETED = 'investigation:completed',
  RUNBOOK_EXECUTION_STARTED = 'runbook:execution:started',
  RUNBOOK_EXECUTION_STEP_COMPLETED = 'runbook:execution:step:completed',
  RUNBOOK_EXECUTION_COMPLETED = 'runbook:execution:completed',
  CHAT_MESSAGE = 'chat:message',
  CHAT_STREAM_CHUNK = 'chat:stream:chunk',
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'admin' | 'operator' | 'viewer';
  teams: string[];
  permissions: string[];
  createdAt: string;
  lastLoginAt?: string;
}

export interface AuthToken {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
  tokenType: 'Bearer';
}

export interface LoginRequest {
  email: string;
  password: string;
  mfaCode?: string;
}

export interface LoginResponse {
  user: AuthUser;
  token: AuthToken;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface RefreshTokenResponse {
  token: AuthToken;
}

export interface ApiConfig {
  baseUrl: string;
  timeout?: number;
  headers?: Record<string, string>;
  withCredentials?: boolean;
}

export interface RequestConfig {
  signal?: AbortSignal;
  timeout?: number;
  headers?: Record<string, string>;
  params?: Record<string, unknown>;
  retry?: {
    count: number;
    delay: number;
    retryOn?: number[];
  };
}
