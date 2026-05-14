import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { api } from '@/lib/api';

// ==================== Types ====================

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'admin' | 'operator' | 'viewer';
  permissions: string[];
  teams?: string[];
  createdAt: string;
  lastLoginAt?: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
  rememberMe?: boolean;
}

export interface RegisterData {
  email: string;
  password: string;
  name: string;
}

export interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  refreshToken: () => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: User['role']) => boolean;
  clearError: () => void;
}

// ==================== Constants ====================

const AUTH_STORAGE_KEY = 'autosre_auth';
const TOKEN_REFRESH_INTERVAL = 4 * 60 * 1000; // 4 minutes

// ==================== Context ====================

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ==================== Provider ====================

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  // Load auth state from storage on mount
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const stored = localStorage.getItem(AUTH_STORAGE_KEY);
        if (stored) {
          const { token, user } = JSON.parse(stored);
          if (token) {
            // Validate token with server
            const validatedUser = await api.get<User>('/v1/auth/me');
            setState({
              user: validatedUser,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
            return;
          }
        }
      } catch {
        // Token invalid or expired, clear storage
        localStorage.removeItem(AUTH_STORAGE_KEY);
      }
      
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    };

    initializeAuth();
  }, []);

  // Set up token refresh interval
  useEffect(() => {
    if (!state.isAuthenticated) return;

    const interval = setInterval(async () => {
      try {
        await refreshToken();
      } catch {
        // Token refresh failed, logout
        await logout();
      }
    }, TOKEN_REFRESH_INTERVAL);

    return () => clearInterval(interval);
  }, [state.isAuthenticated]);

  const login = useCallback(async (credentials: LoginCredentials) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await api.post<{ token: string; user: User }>('/v1/auth/login', credentials);
      
      // Store auth data
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
        token: response.token,
        user: response.user,
        rememberMe: credentials.rememberMe,
      }));

      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/v1/auth/logout');
    } catch {
      // Ignore logout errors
    }

    localStorage.removeItem(AUTH_STORAGE_KEY);
    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  }, []);

  const register = useCallback(async (data: RegisterData) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await api.post<{ token: string; user: User }>('/v1/auth/register', data);
      
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({
        token: response.token,
        user: response.user,
      }));

      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw err;
    }
  }, []);

  const refreshToken = useCallback(async () => {
    try {
      const response = await api.post<{ token: string }>('/v1/auth/refresh');
      
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored) {
        const data = JSON.parse(stored);
        data.token = response.token;
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(data));
      }
    } catch (err) {
      throw err;
    }
  }, []);

  const updateProfile = useCallback(async (data: Partial<User>) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const updatedUser = await api.patch<User>('/v1/auth/profile', data);
      
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored) {
        const authData = JSON.parse(stored);
        authData.user = updatedUser;
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(authData));
      }

      setState(prev => ({
        ...prev,
        user: updatedUser,
        isLoading: false,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Profile update failed';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw err;
    }
  }, []);

  const changePassword = useCallback(async (oldPassword: string, newPassword: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      await api.post('/v1/auth/change-password', { oldPassword, newPassword });
      setState(prev => ({ ...prev, isLoading: false }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Password change failed';
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw err;
    }
  }, []);

  const hasPermission = useCallback((permission: string): boolean => {
    if (!state.user) return false;
    
    // Admin has all permissions
    if (state.user.role === 'admin') return true;
    
    return state.user.permissions.includes(permission);
  }, [state.user]);

  const hasRole = useCallback((role: User['role']): boolean => {
    if (!state.user) return false;
    
    const roleHierarchy: Record<User['role'], number> = {
      admin: 3,
      operator: 2,
      viewer: 1,
    };
    
    return roleHierarchy[state.user.role] >= roleHierarchy[role];
  }, [state.user]);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  const value: AuthContextType = {
    ...state,
    login,
    logout,
    register,
    refreshToken,
    updateProfile,
    changePassword,
    hasPermission,
    hasRole,
    clearError,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// ==================== Hooks ====================

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function useUser(): User | null {
  const { user } = useAuth();
  return user;
}

export function useIsAuthenticated(): boolean {
  const { isAuthenticated } = useAuth();
  return isAuthenticated;
}

export function usePermissions() {
  const { hasPermission, hasRole, user } = useAuth();
  return { hasPermission, hasRole, permissions: user?.permissions ?? [] };
}

// ==================== Permission Constants ====================

export const PERMISSIONS = {
  // Alert permissions
  ALERTS_VIEW: 'alerts:view',
  ALERTS_ACKNOWLEDGE: 'alerts:acknowledge',
  ALERTS_RESOLVE: 'alerts:resolve',
  ALERTS_INVESTIGATE: 'alerts:investigate',
  
  // Investigation permissions
  INVESTIGATIONS_VIEW: 'investigations:view',
  INVESTIGATIONS_APPROVE: 'investigations:approve',
  INVESTIGATIONS_CANCEL: 'investigations:cancel',
  
  // Runbook permissions
  RUNBOOKS_VIEW: 'runbooks:view',
  RUNBOOKS_CREATE: 'runbooks:create',
  RUNBOOKS_EDIT: 'runbooks:edit',
  RUNBOOKS_DELETE: 'runbooks:delete',
  RUNBOOKS_EXECUTE: 'runbooks:execute',
  
  // Chat permissions
  CHAT_VIEW: 'chat:view',
  CHAT_SEND: 'chat:send',
  
  // Admin permissions
  ADMIN_USERS: 'admin:users',
  ADMIN_SETTINGS: 'admin:settings',
  ADMIN_INTEGRATIONS: 'admin:integrations',
} as const;

export type Permission = typeof PERMISSIONS[keyof typeof PERMISSIONS];
