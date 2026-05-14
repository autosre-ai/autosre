import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Sun, Moon, Bell, Search } from 'lucide-react';
import { useState } from 'react';

interface HeaderProps {
  title: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
}

export function Header({ title, subtitle, actions, className }: HeaderProps) {
  const [isDark, setIsDark] = useState(true);

  const toggleTheme = () => {
    setIsDark(!isDark);
    document.documentElement.classList.toggle('dark');
  };

  return (
    <header
      className={cn(
        'sticky top-0 z-30 bg-white/80 dark:bg-stone-900/80 backdrop-blur-sm',
        'border-b border-stone-200 dark:border-stone-800',
        className
      )}
    >
      <div className="px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl lg:text-2xl font-bold text-stone-900 dark:text-white truncate">
              {title}
            </h1>
            {subtitle && (
              <p className="text-sm text-stone-500 mt-0.5 truncate">{subtitle}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Search */}
            <button className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors hidden sm:block">
              <Search className="w-5 h-5" />
            </button>

            {/* Notifications */}
            <button className="relative p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
            </button>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            {/* Actions */}
            {actions}
          </div>
        </div>
      </div>
    </header>
  );
}
