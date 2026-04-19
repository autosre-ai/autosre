'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { Search, Bell, Command, User, Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useCommandPalette, useSidebar } from '@/lib/store';
import { useKeyboardShortcuts, SHORTCUTS } from '@/hooks/use-keyboard';
import { cn } from '@/lib/utils';

interface HeaderProps {
  pendingApprovals?: number;
  activeIncidents?: number;
}

export function Header({ pendingApprovals = 0, activeIncidents = 0 }: HeaderProps) {
  const router = useRouter();
  const { isCollapsed } = useSidebar();
  const { open: openCommandPalette } = useCommandPalette();
  const [searchFocused, setSearchFocused] = React.useState(false);

  useKeyboardShortcuts({
    [SHORTCUTS.COMMAND_PALETTE]: openCommandPalette,
    [SHORTCUTS.GO_HOME]: () => router.push('/'),
    [SHORTCUTS.GO_INCIDENTS]: () => router.push('/incidents'),
    [SHORTCUTS.GO_AGENTS]: () => router.push('/agents'),
    [SHORTCUTS.GO_SETTINGS]: () => router.push('/settings'),
  });

  return (
    <header
      className={cn(
        'fixed top-0 right-0 z-30 h-16 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm transition-all duration-300',
        isCollapsed ? 'left-16' : 'left-64'
      )}
    >
      <div className="flex h-full items-center justify-between px-6">
        {/* Search */}
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
            <Input
              placeholder="Search incidents, agents..."
              className={cn(
                'w-64 pl-10 transition-all',
                searchFocused && 'w-80'
              )}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 text-xs font-mono bg-gray-800 border border-gray-700 rounded">⌘</kbd>
              <kbd className="px-1.5 py-0.5 text-xs font-mono bg-gray-800 border border-gray-700 rounded">K</kbd>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Active incidents indicator */}
          {activeIncidents > 0 && (
            <Button variant="ghost" size="sm" className="gap-2 text-yellow-400" onClick={() => router.push('/incidents')}>
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-yellow-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-yellow-500"></span>
              </span>
              <span className="text-sm">{activeIncidents} active</span>
            </Button>
          )}

          {/* Pending approvals */}
          {pendingApprovals > 0 && (
            <Button variant="ghost" size="sm" className="relative" onClick={() => router.push('/incidents')}>
              <Bell className="h-5 w-5" />
              <Badge variant="danger" className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center">
                {pendingApprovals}
              </Badge>
            </Button>
          )}

          {/* Command palette */}
          <Button variant="ghost" size="icon" onClick={openCommandPalette}>
            <Command className="h-5 w-5" />
          </Button>

          {/* User menu */}
          <Button variant="ghost" size="icon">
            <User className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </header>
  );
}
