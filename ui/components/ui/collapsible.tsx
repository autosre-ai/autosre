'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface CollapsibleProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
  className?: string;
}

const CollapsibleContext = React.createContext<{
  open: boolean;
  toggle: () => void;
}>({ open: false, toggle: () => {} });

export function Collapsible({
  open: controlledOpen,
  onOpenChange,
  children,
  className,
}: CollapsibleProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(false);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const toggle = React.useCallback(() => {
    if (isControlled) {
      onOpenChange?.(!open);
    } else {
      setUncontrolledOpen(!open);
    }
  }, [isControlled, onOpenChange, open]);

  return (
    <CollapsibleContext.Provider value={{ open, toggle }}>
      <div className={cn('', className)}>{children}</div>
    </CollapsibleContext.Provider>
  );
}

export function CollapsibleTrigger({
  children,
  className,
  asChild,
}: {
  children: React.ReactNode;
  className?: string;
  asChild?: boolean;
}) {
  const { open, toggle } = React.useContext(CollapsibleContext);

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children, {
      onClick: toggle,
    } as React.HTMLAttributes<HTMLElement>);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className={cn('flex items-center gap-2 w-full', className)}
    >
      {open ? (
        <ChevronDown className="h-4 w-4 shrink-0" />
      ) : (
        <ChevronRight className="h-4 w-4 shrink-0" />
      )}
      {children}
    </button>
  );
}

export function CollapsibleContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const { open } = React.useContext(CollapsibleContext);

  if (!open) return null;

  return <div className={cn('', className)}>{children}</div>;
}
