import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback, useState } from 'react';
import { api } from '@/lib/api';
import type { HealthResponse, HealthStatus, ComponentHealth } from '@/types';

// Dashboard-specific types (client-side only)
export interface DashboardMetrics {
  activeAlerts: number;
  criticalAlerts: number;
  activeInvestigations: number;
  mttr: number;
  alertsToday: number;
  investigationsToday: number;
}

export interface SystemHealth {
  status: HealthStatus;
  services: ServiceHealth[];
  lastUpdated: string;
}

export interface MetricDataPoint {
  timestamp: string;
  value: number;
}

export interface MetricSeries {
  name: string;
  data: MetricDataPoint[];
  color?: string;
}

// ==================== Types ====================
export interface ServiceHealth {
  name: string;
  status: HealthStatus;
  latencyP99: number;
  errorRate: number;
  uptime?: number;
  lastChecked?: string;
}

export interface HealthCheckResult {
  api: boolean;
  database: boolean;
  cache: boolean;
  messageQueue: boolean;
  integrations: Record<string, boolean>;
}

export interface MetricsTimeRange {
  start: string;
  end: string;
  step?: string; // e.g., '1m', '5m', '1h'
}

// ==================== Query Keys ====================
export const healthKeys = {
  all: ['health'] as const,
  system: () => [...healthKeys.all, 'system'] as const,
  services: () => [...healthKeys.all, 'services'] as const,
  service: (name: string) => [...healthKeys.services(), name] as const,
  checks: () => [...healthKeys.all, 'checks'] as const,
  dashboard: () => ['dashboard'] as const,
  metrics: () => [...healthKeys.dashboard(), 'metrics'] as const,
  timeSeries: (metric: string, range?: MetricsTimeRange) => 
    [...healthKeys.dashboard(), 'timeseries', metric, range] as const,
};

// ==================== Queries ====================

/**
 * Fetch overall system health status
 * Auto-refetches every 15 seconds
 */
export function useSystemHealth() {
  return useQuery({
    queryKey: healthKeys.system(),
    queryFn: async (): Promise<SystemHealth> => {
      const response = await api.get<HealthResponse>('/v1/health');
      return {
        status: response.status,
        services: response.components.map((c: ComponentHealth) => ({
          name: c.name,
          status: c.status,
          latencyP99: c.latencyMs || 0,
          errorRate: c.status === 'unhealthy' ? 100 : c.status === 'degraded' ? 50 : 0,
        })),
        lastUpdated: response.timestamp,
      };
    },
    refetchInterval: 15000,
    staleTime: 10000,
    // Retry aggressively for health checks
    retry: 3,
    retryDelay: 1000,
  });
}

/**
 * Fetch dashboard metrics (alert counts, MTTR, etc.)
 * Auto-refetches every 30 seconds
 */
export function useDashboardMetrics() {
  return useQuery({
    queryKey: healthKeys.metrics(),
    queryFn: () => api.get<DashboardMetrics>('/v1/dashboard/metrics'),
    refetchInterval: 30000,
    staleTime: 15000,
  });
}

/**
 * Fetch health status for all services
 */
export function useServicesHealth() {
  return useQuery({
    queryKey: healthKeys.services(),
    queryFn: () => api.get<ServiceHealth[]>('/v1/health/services'),
    refetchInterval: 30000,
    staleTime: 15000,
  });
}

/**
 * Fetch health status for a specific service
 */
export function useServiceHealth(serviceName: string) {
  return useQuery({
    queryKey: healthKeys.service(serviceName),
    queryFn: () => api.get<ServiceHealth>(`/v1/health/services/${serviceName}`),
    enabled: !!serviceName,
    refetchInterval: 15000,
  });
}

/**
 * Run health checks for all system components
 */
export function useHealthChecks() {
  return useQuery({
    queryKey: healthKeys.checks(),
    queryFn: () => api.get<HealthCheckResult>('/v1/health/check'),
    staleTime: 60000,
    // Don't auto-refresh, only on demand
    refetchOnWindowFocus: false,
  });
}

/**
 * Fetch time series metrics for charts
 */
export function useMetricsTimeSeries(
  metric: 'alerts' | 'investigations' | 'mttr' | 'error_rate' | 'latency',
  range?: MetricsTimeRange
) {
  return useQuery({
    queryKey: healthKeys.timeSeries(metric, range),
    queryFn: async () => {
      const params: Record<string, string> = { metric };
      if (range?.start) params.start = range.start;
      if (range?.end) params.end = range.end;
      if (range?.step) params.step = range.step;
      
      return api.get<MetricSeries[]>('/v1/dashboard/metrics/timeseries', params);
    },
    staleTime: 60000,
    refetchInterval: 60000,
  });
}

/**
 * Fetch alert trend data for the dashboard
 */
export function useAlertTrends(days: number = 7) {
  return useQuery({
    queryKey: [...healthKeys.dashboard(), 'alert-trends', days],
    queryFn: () => api.get<MetricSeries[]>(`/v1/dashboard/alerts/trends?days=${days}`),
    staleTime: 300000, // 5 minutes
  });
}

/**
 * Fetch investigation trends
 */
export function useInvestigationTrends(days: number = 7) {
  return useQuery({
    queryKey: [...healthKeys.dashboard(), 'investigation-trends', days],
    queryFn: () => api.get<MetricSeries[]>(`/v1/dashboard/investigations/trends?days=${days}`),
    staleTime: 300000,
  });
}

// ==================== Real-time Updates ====================

/**
 * Subscribe to real-time health updates via SSE
 */
export function useHealthStream() {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const connect = useCallback(() => {
    const eventSource = new EventSource('/api/v1/health/stream');
    
    eventSource.onopen = () => {
      setIsConnected(true);
    };
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastUpdate(new Date().toISOString());
        
        // Update relevant caches based on event type
        if (data.type === 'system_health') {
          queryClient.setQueryData(healthKeys.system(), data.payload);
        } else if (data.type === 'service_health') {
          queryClient.setQueryData(
            healthKeys.service(data.payload.name),
            data.payload
          );
        } else if (data.type === 'metrics') {
          queryClient.setQueryData(healthKeys.metrics(), data.payload);
        }
      } catch (e) {
        console.error('Failed to parse health stream event:', e);
      }
    };
    
    eventSource.onerror = () => {
      setIsConnected(false);
      eventSource.close();
      // Reconnect after 5 seconds
      setTimeout(connect, 5000);
    };
    
    return eventSource;
  }, [queryClient]);

  useEffect(() => {
    const eventSource = connect();
    return () => eventSource.close();
  }, [connect]);

  return { isConnected, lastUpdate };
}

// ==================== Utility Hooks ====================

/**
 * Calculate overall system status from health data
 */
export function useOverallStatus() {
  const { data: health } = useSystemHealth();
  const { data: metrics } = useDashboardMetrics();

  if (!health || !metrics) {
    return { status: 'unknown' as const, message: 'Loading...' };
  }

  if (health.status === 'unhealthy') {
    return { status: 'critical' as const, message: 'System outage detected' };
  }

  if (metrics.criticalAlerts > 0) {
    return { 
      status: 'critical' as const, 
      message: `${metrics.criticalAlerts} critical alert(s) firing` 
    };
  }

  if (health.status === 'degraded') {
    const degradedServices = health.services.filter((s: ServiceHealth) => s.status !== 'healthy');
    return { 
      status: 'warning' as const, 
      message: `${degradedServices.length} service(s) degraded` 
    };
  }

  if (metrics.activeAlerts > 5) {
    return { 
      status: 'warning' as const, 
      message: `${metrics.activeAlerts} active alerts` 
    };
  }

  return { status: 'healthy' as const, message: 'All systems operational' };
}

/**
 * Prefetch dashboard data for faster initial load
 */
export function usePrefetchDashboard() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.prefetchQuery({
      queryKey: healthKeys.system(),
      queryFn: () => api.get<SystemHealth>('/v1/dashboard/health'),
    });
    
    queryClient.prefetchQuery({
      queryKey: healthKeys.metrics(),
      queryFn: () => api.get<DashboardMetrics>('/v1/dashboard/metrics'),
    });
  }, [queryClient]);
}

/**
 * Force refresh all health data
 */
export function useRefreshHealth() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: healthKeys.all });
    queryClient.invalidateQueries({ queryKey: healthKeys.dashboard() });
  }, [queryClient]);
}
