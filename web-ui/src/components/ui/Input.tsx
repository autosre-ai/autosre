import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
    
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'w-full px-3 py-2 rounded-lg border bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100',
            'placeholder:text-stone-400 dark:placeholder:text-stone-500',
            'focus:outline-none focus:ring-2 focus:ring-forest/50 focus:border-forest',
            'transition-colors duration-200',
            error ? 'border-red-500 focus:ring-red-500/50 focus:border-red-500' : 'border-stone-300 dark:border-stone-600',
            className
          )}
          {...props}
        />
        {error && <p className="mt-1.5 text-sm text-red-600 dark:text-red-400">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';
