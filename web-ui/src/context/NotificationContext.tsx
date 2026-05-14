import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  type ReactNode,
} from 'react';

// ==================== Types ====================

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message?: string;
  duration?: number; // ms, 0 for persistent
  dismissible?: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
  createdAt: number;
}

export interface NotificationOptions {
  title: string;
  message?: string;
  type?: NotificationType;
  duration?: number;
  dismissible?: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface NotificationState {
  notifications: Notification[];
  maxNotifications: number;
}

type NotificationAction =
  | { type: 'ADD'; notification: Notification }
  | { type: 'REMOVE'; id: string }
  | { type: 'CLEAR_ALL' }
  | { type: 'SET_MAX'; max: number };

interface NotificationContextType {
  notifications: Notification[];
  notify: (options: NotificationOptions) => string;
  success: (title: string, message?: string) => string;
  error: (title: string, message?: string) => string;
  warning: (title: string, message?: string) => string;
  info: (title: string, message?: string) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
}

// ==================== Constants ====================

const DEFAULT_DURATION: Record<NotificationType, number> = {
  success: 3000,
  error: 5000,
  warning: 4000,
  info: 3000,
};

const MAX_NOTIFICATIONS = 5;

// ==================== Reducer ====================

function notificationReducer(
  state: NotificationState,
  action: NotificationAction
): NotificationState {
  switch (action.type) {
    case 'ADD': {
      const notifications = [action.notification, ...state.notifications];
      // Remove oldest notifications if exceeding max
      return {
        ...state,
        notifications: notifications.slice(0, state.maxNotifications),
      };
    }
    case 'REMOVE':
      return {
        ...state,
        notifications: state.notifications.filter(n => n.id !== action.id),
      };
    case 'CLEAR_ALL':
      return {
        ...state,
        notifications: [],
      };
    case 'SET_MAX':
      return {
        ...state,
        maxNotifications: action.max,
        notifications: state.notifications.slice(0, action.max),
      };
    default:
      return state;
  }
}

// ==================== Context ====================

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

// ==================== Provider ====================

interface NotificationProviderProps {
  children: ReactNode;
  maxNotifications?: number;
}

export function NotificationProvider({
  children,
  maxNotifications = MAX_NOTIFICATIONS,
}: NotificationProviderProps) {
  const [state, dispatch] = useReducer(notificationReducer, {
    notifications: [],
    maxNotifications,
  });

  const notify = useCallback((options: NotificationOptions): string => {
    const id = `notification-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const type = options.type ?? 'info';
    const duration = options.duration ?? DEFAULT_DURATION[type];
    const dismissible = options.dismissible ?? true;

    const notification: Notification = {
      id,
      type,
      title: options.title,
      message: options.message,
      duration,
      dismissible,
      action: options.action,
      createdAt: Date.now(),
    };

    dispatch({ type: 'ADD', notification });

    // Auto-dismiss after duration
    if (duration > 0) {
      setTimeout(() => {
        dispatch({ type: 'REMOVE', id });
      }, duration);
    }

    return id;
  }, []);

  const success = useCallback(
    (title: string, message?: string): string => {
      return notify({ type: 'success', title, message });
    },
    [notify]
  );

  const error = useCallback(
    (title: string, message?: string): string => {
      return notify({ type: 'error', title, message });
    },
    [notify]
  );

  const warning = useCallback(
    (title: string, message?: string): string => {
      return notify({ type: 'warning', title, message });
    },
    [notify]
  );

  const info = useCallback(
    (title: string, message?: string): string => {
      return notify({ type: 'info', title, message });
    },
    [notify]
  );

  const dismiss = useCallback((id: string) => {
    dispatch({ type: 'REMOVE', id });
  }, []);

  const dismissAll = useCallback(() => {
    dispatch({ type: 'CLEAR_ALL' });
  }, []);

  const value: NotificationContextType = {
    notifications: state.notifications,
    notify,
    success,
    error,
    warning,
    info,
    dismiss,
    dismissAll,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

// ==================== Hooks ====================

export function useNotifications(): NotificationContextType {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}

/**
 * Simple hook for quick toast access
 */
export function useToast() {
  const { success, error, warning, info, dismiss } = useNotifications();
  return { success, error, warning, info, dismiss };
}

// ==================== Notification Component (Optional) ====================

import { useEffect, useState } from 'react';

interface ToastProps {
  notification: Notification;
  onDismiss: (id: string) => void;
}

const typeStyles: Record<NotificationType, { bg: string; icon: string; border: string }> = {
  success: {
    bg: 'bg-green-50 dark:bg-green-900/20',
    border: 'border-green-200 dark:border-green-800',
    icon: '✓',
  },
  error: {
    bg: 'bg-red-50 dark:bg-red-900/20',
    border: 'border-red-200 dark:border-red-800',
    icon: '✕',
  },
  warning: {
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    border: 'border-yellow-200 dark:border-yellow-800',
    icon: '⚠',
  },
  info: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    border: 'border-blue-200 dark:border-blue-800',
    icon: 'ℹ',
  },
};

export function Toast({ notification, onDismiss }: ToastProps) {
  const [isExiting, setIsExiting] = useState(false);
  const styles = typeStyles[notification.type];

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => {
      onDismiss(notification.id);
    }, 150);
  };

  // Progress bar for auto-dismiss
  const showProgress = notification.duration && notification.duration > 0;

  return (
    <div
      className={`
        relative overflow-hidden rounded-lg border shadow-lg
        transition-all duration-150 ease-in-out
        ${styles.bg} ${styles.border}
        ${isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'}
      `}
      role="alert"
    >
      <div className="flex items-start gap-3 p-4">
        {/* Icon */}
        <span className="flex-shrink-0 text-lg">{styles.icon}</span>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 dark:text-gray-100">
            {notification.title}
          </p>
          {notification.message && (
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              {notification.message}
            </p>
          )}
          {notification.action && (
            <button
              onClick={notification.action.onClick}
              className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
            >
              {notification.action.label}
            </button>
          )}
        </div>

        {/* Dismiss button */}
        {notification.dismissible && (
          <button
            onClick={handleDismiss}
            className="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            aria-label="Dismiss"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Progress bar */}
      {showProgress && (
        <div
          className="absolute bottom-0 left-0 h-1 bg-current opacity-20"
          style={{
            animation: `shrink ${notification.duration}ms linear forwards`,
          }}
        />
      )}

      <style>{`
        @keyframes shrink {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
}

/**
 * Toast container component - place this in your app layout
 */
export function ToastContainer() {
  const { notifications, dismiss } = useNotifications();

  if (notifications.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm"
      aria-live="polite"
      aria-label="Notifications"
    >
      {notifications.map(notification => (
        <Toast
          key={notification.id}
          notification={notification}
          onDismiss={dismiss}
        />
      ))}
    </div>
  );
}
