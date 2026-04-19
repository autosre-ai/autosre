'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  maxHeight?: string | number;
}

export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, maxHeight, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('overflow-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent', className)}
        style={{ maxHeight }}
        {...props}
      >
        {children}
      </div>
    );
  }
);
ScrollArea.displayName = 'ScrollArea';
