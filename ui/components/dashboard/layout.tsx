'use client';

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from '@/components/dashboard/sidebar';
import { Header } from '@/components/dashboard/header';
import { CommandPalette } from '@/components/dashboard/command-palette';
import { useSidebar } from '@/lib/store';
import { cn } from '@/lib/utils';
import { useInvestigations } from '@/hooks/use-api';

// Create query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();
  const { data: investigations } = useInvestigations();
  
  const activeIncidents = investigations?.filter(i => i.status === 'running').length || 0;
  const pendingApprovals = investigations?.reduce(
    (count, inv) => count + inv.actions.filter(a => a.status === 'pending' && a.requires_approval).length,
    0
  ) || 0;

  return (
    <div className="min-h-screen bg-gray-950">
      <Sidebar />
      <Header pendingApprovals={pendingApprovals} activeIncidents={activeIncidents} />
      <CommandPalette />
      
      <main
        className={cn(
          'pt-16 min-h-screen transition-all duration-300',
          isCollapsed ? 'pl-16' : 'pl-64'
        )}
      >
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  );
}

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </QueryClientProvider>
  );
}
