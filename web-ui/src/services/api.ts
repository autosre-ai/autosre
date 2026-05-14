/**
 * AutoSRE V2 - Base API Client
 * 
 * Axios-based HTTP client with authentication, error handling,
 * and request/response interceptors.
 */

import axios, {
  type AxiosInstance,
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';
import type { ApiError, ApiErrorResponse, ApiResponse } from '../types';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const API_TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT) || 30000;

// Token storage keys
const ACCESS_TOKEN_KEY = 'autosre_access_token';
const REFRESH_TOKEN_KEY = 'autosre_refresh_token';

/**
 * Custom API error class for better error handling
 */
export class ApiException extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly details?: Record<string, unknown>;
  public readonly requestId?: string;

  constructor(error: ApiError, status: number) {
    super(error.message);
    this.name = 'ApiException';
    this.code = error.code;
    this.status = status;
    this.details = error.details;
    this.requestId = error.requestId;
  }

  static fromAxiosError(error: AxiosError<ApiErrorResponse>): ApiException {
    if (error.response?.data?.error) {
      return new ApiException(error.response.data.error, error.response.status);
    }

    return new ApiException(
      {
        code: 'NETWORK_ERROR',
        message: error.message || 'An unexpected error occurred',
        timestamp: new Date().toISOString(),
      },
      error.response?.status || 0
    );
  }
}

/**
 * Token management utilities
 */
export const tokenManager = {
  getAccessToken: (): string | null => {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken: (): string | null => {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setTokens: (accessToken: string, refreshToken: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  isAuthenticated: (): boolean => {
    return !!localStorage.getItem(ACCESS_TOKEN_KEY);
  },
};

/**
 * Create and configure the Axios instance
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: API_TIMEOUT,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
  });

  // Request interceptor - Add auth token
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = tokenManager.getAccessToken();
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Add request ID for tracing
      config.headers['X-Request-ID'] = crypto.randomUUID();

      return config;
    },
    (error: AxiosError) => {
      return Promise.reject(error);
    }
  );

  // Response interceptor - Handle errors and token refresh
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError<ApiErrorResponse>) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & {
        _retry?: boolean;
      };

      // Handle 401 - Attempt token refresh
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;

        const refreshToken = tokenManager.getRefreshToken();
        if (refreshToken) {
          try {
            const response = await axios.post<{
              data: { token: { accessToken: string; refreshToken: string } };
            }>(`${API_BASE_URL}/auth/refresh`, { refreshToken });

            const { accessToken, refreshToken: newRefreshToken } =
              response.data.data.token;
            tokenManager.setTokens(accessToken, newRefreshToken);

            // Retry the original request
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${accessToken}`;
            }
            return client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - clear tokens and redirect to login
            tokenManager.clearTokens();
            window.dispatchEvent(new CustomEvent('auth:logout'));
            return Promise.reject(refreshError);
          }
        }
      }

      // Transform error to ApiException
      throw ApiException.fromAxiosError(error);
    }
  );

  return client;
};

// Export singleton instance
const api = createApiClient();

export default api;

/**
 * Helper type for unwrapping API responses
 */
export type UnwrapApiResponse<T> = T extends ApiResponse<infer U> ? U : never;

/**
 * Request helper with automatic response unwrapping
 */
export async function apiRequest<T>(
  config: AxiosRequestConfig
): Promise<T> {
  const response = await api.request<ApiResponse<T>>(config);
  if (!response.data.success) {
    throw new ApiException(
      response.data.error || {
        code: 'UNKNOWN_ERROR',
        message: 'Request failed',
        timestamp: new Date().toISOString(),
      },
      response.status
    );
  }
  return response.data.data as T;
}

/**
 * Type-safe GET request
 */
export async function apiGet<T>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  return apiRequest<T>({ ...config, method: 'GET', url });
}

/**
 * Type-safe POST request
 */
export async function apiPost<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  return apiRequest<T>({ ...config, method: 'POST', url, data });
}

/**
 * Type-safe PUT request
 */
export async function apiPut<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  return apiRequest<T>({ ...config, method: 'PUT', url, data });
}

/**
 * Type-safe PATCH request
 */
export async function apiPatch<T, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  return apiRequest<T>({ ...config, method: 'PATCH', url, data });
}

/**
 * Type-safe DELETE request
 */
export async function apiDelete<T = void>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  return apiRequest<T>({ ...config, method: 'DELETE', url });
}
