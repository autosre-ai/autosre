'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/lib/store';
import {
  Shield,
  LayoutDashboard,
  AlertTriangle,
  Bot,
  Wrench,
  BookOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
} from 'lucide-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { href: '/agents', label: 'Agents', icon: Bot },
  { href: '/skills', label: 'Skills', icon: Wrench },
  { href: '/runbooks', label: 'Runbooks', icon: BookOpen },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggle } = useSidebar();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen border-r border-gray-800 bg-gray-900 transition-all duration-300',
        isCollapsed ? 'w-16' : 'w-64'
      )}
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center justify-between border-b border-gray-800 px-4">
          <Link href="/" className="flex items-center gap-3">
            <Shield className="h-8 w-8 text-blue-500" />
            {!isCollapsed && (
              <div>
                <h1 className="text-lg font-bold">OpenSRE</h1>
                <p className="text-xs text-gray-500">AI Ops Platform</p>
              </div>
            )}
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-2 py-4">
          {navItems.map((item) => {
            const isActive = pathname === item.href || 
              (item.href !== '/' && pathname.startsWith(item.href));
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-500/10 text-blue-400'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                )}
              >
                <Icon className={cn('h-5 w-5 shrink-0', isActive && 'text-blue-400')} />
                {!isCollapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Status indicator */}
        <div className="border-t border-gray-800 p-4">
          <div className={cn('flex items-center gap-3', isCollapsed && 'justify-center')}>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-500" />
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            </div>
            {!isCollapsed && (
              <span className="text-xs text-gray-400">System Operational</span>
            )}
          </div>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={toggle}
          className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-gray-700 bg-gray-800 text-gray-400 hover:text-white"
        >
          {isCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
