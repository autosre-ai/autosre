/**
 * AutoSRE V2 - Context Providers
 *
 * Re-exports all context providers and hooks for convenient imports.
 *
 * Usage:
 *   import { AuthProvider, useAuth, ThemeProvider, useTheme } from '@/context';
 */

// ==================== Auth Context ====================
export {
  AuthProvider,
  useAuth,
  useUser,
  useIsAuthenticated,
  usePermissions,
  PERMISSIONS,
  type User,
  type AuthState,
  type LoginCredentials,
  type RegisterData,
  type AuthContextType,
  type Permission,
} from './AuthContext';

// ==================== Theme Context ====================
export {
  ThemeProvider,
  useTheme,
} from './ThemeContext';

// ==================== Notification Context ====================
export {
  NotificationProvider,
  useNotifications,
  useToast,
  Toast,
  ToastContainer,
  type Notification,
  type NotificationType,
  type NotificationOptions,
} from './NotificationContext';
