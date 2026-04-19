'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  Home,
  AlertTriangle,
  Bot,
  Settings,
  Wrench,
  BookOpen,
  Plus,
  ArrowRight,
} from 'lucide-react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useCommandPalette } from '@/lib/store';
import { useKeyboardShortcuts } from '@/hooks/use-keyboard';
import { cn } from '@/lib/utils';

interface Command {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  shortcut?: string;
  action: () => void;
  category: string;
}

export function CommandPalette() {
  const router = useRouter();
  const { isOpen, close } = useCommandPalette();
  const [search, setSearch] = React.useState('');
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const commands: Command[] = React.useMemo(
    () => [
      // Navigation
      { id: 'home', label: 'Go to Dashboard', icon: Home, shortcut: 'G H', action: () => router.push('/'), category: 'Navigation' },
      { id: 'incidents', label: 'Go to Incidents', icon: AlertTriangle, shortcut: 'G I', action: () => router.push('/incidents'), category: 'Navigation' },
      { id: 'agents', label: 'Go to Agents', icon: Bot, shortcut: 'G A', action: () => router.push('/agents'), category: 'Navigation' },
      { id: 'skills', label: 'Go to Skills', icon: Wrench, action: () => router.push('/skills'), category: 'Navigation' },
      { id: 'runbooks', label: 'Go to Runbooks', icon: BookOpen, action: () => router.push('/runbooks'), category: 'Navigation' },
      { id: 'settings', label: 'Go to Settings', icon: Settings, shortcut: 'G S', action: () => router.push('/settings'), category: 'Navigation' },
      // Actions
      { id: 'new-incident', label: 'Create New Investigation', icon: Plus, shortcut: '⌘ N', action: () => router.push('/incidents?new=true'), category: 'Actions' },
    ],
    [router]
  );

  const filteredCommands = React.useMemo(() => {
    if (!search) return commands;
    const lower = search.toLowerCase();
    return commands.filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(lower) ||
        cmd.category.toLowerCase().includes(lower)
    );
  }, [commands, search]);

  const groupedCommands = React.useMemo(() => {
    const groups: Record<string, Command[]> = {};
    filteredCommands.forEach((cmd) => {
      if (!groups[cmd.category]) groups[cmd.category] = [];
      groups[cmd.category].push(cmd);
    });
    return groups;
  }, [filteredCommands]);

  const handleSelect = React.useCallback(
    (command: Command) => {
      command.action();
      close();
      setSearch('');
    },
    [close]
  );

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filteredCommands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          handleSelect(filteredCommands[selectedIndex]);
        }
      }
    },
    [filteredCommands, selectedIndex, handleSelect]
  );

  React.useEffect(() => {
    if (isOpen) {
      setSearch('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [isOpen]);

  useKeyboardShortcuts({
    escape: close,
  });

  let flatIndex = 0;

  return (
    <Dialog open={isOpen} onOpenChange={close}>
      <DialogContent className="max-w-xl p-0 overflow-hidden" onClose={close}>
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-gray-800 px-4">
          <Search className="h-5 w-5 text-gray-500" />
          <Input
            ref={inputRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="border-0 bg-transparent focus-visible:ring-0 px-0"
          />
        </div>

        {/* Commands list */}
        <div className="max-h-80 overflow-auto py-2">
          {Object.entries(groupedCommands).map(([category, cmds]) => (
            <div key={category}>
              <div className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {category}
              </div>
              {cmds.map((cmd) => {
                const currentIndex = flatIndex++;
                const isSelected = selectedIndex === currentIndex;
                const Icon = cmd.icon;

                return (
                  <button
                    key={cmd.id}
                    onClick={() => handleSelect(cmd)}
                    onMouseEnter={() => setSelectedIndex(currentIndex)}
                    className={cn(
                      'flex w-full items-center justify-between px-4 py-2 text-sm',
                      isSelected ? 'bg-blue-500/20 text-blue-400' : 'text-gray-300 hover:bg-gray-800'
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="h-4 w-4" />
                      <span>{cmd.label}</span>
                    </div>
                    {cmd.shortcut && (
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        {cmd.shortcut.split(' ').map((key, i) => (
                          <kbd
                            key={i}
                            className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded"
                          >
                            {key}
                          </kbd>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}

          {filteredCommands.length === 0 && (
            <div className="px-4 py-8 text-center text-gray-500">
              No commands found
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-800 px-4 py-2 text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 bg-gray-800 rounded">↑↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 bg-gray-800 rounded">↵</kbd>
              select
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 bg-gray-800 rounded">esc</kbd>
              close
            </span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
