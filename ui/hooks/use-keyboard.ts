'use client';

import { useEffect, useCallback } from 'react';

type KeyCombo = string[];
type Handler = () => void;

interface Shortcut {
  keys: KeyCombo;
  handler: Handler;
  description?: string;
}

const parseKeyCombo = (combo: string): KeyCombo => {
  return combo.toLowerCase().split('+').map(k => k.trim());
};

const matchesCombo = (event: KeyboardEvent, combo: KeyCombo): boolean => {
  const pressedKeys: string[] = [];
  
  if (event.metaKey || event.ctrlKey) pressedKeys.push('mod');
  if (event.shiftKey) pressedKeys.push('shift');
  if (event.altKey) pressedKeys.push('alt');
  
  const key = event.key.toLowerCase();
  if (!['meta', 'control', 'shift', 'alt'].includes(key)) {
    pressedKeys.push(key);
  }
  
  const normalizedCombo = combo.map(k => {
    if (k === 'cmd' || k === 'ctrl') return 'mod';
    return k;
  });
  
  return (
    pressedKeys.length === normalizedCombo.length &&
    normalizedCombo.every(k => pressedKeys.includes(k))
  );
};

export function useKeyboardShortcuts(shortcuts: Record<string, Handler>) {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        (event.target as HTMLElement).isContentEditable
      ) {
        return;
      }

      for (const [combo, handler] of Object.entries(shortcuts)) {
        if (matchesCombo(event, parseKeyCombo(combo))) {
          event.preventDefault();
          handler();
          return;
        }
      }
    },
    [shortcuts]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

// Common shortcuts
export const SHORTCUTS = {
  COMMAND_PALETTE: 'mod+k',
  SEARCH: 'mod+/',
  NEW_INCIDENT: 'mod+n',
  GO_HOME: 'g+h',
  GO_INCIDENTS: 'g+i',
  GO_AGENTS: 'g+a',
  GO_SETTINGS: 'g+s',
  REFRESH: 'mod+r',
  ESCAPE: 'escape',
};
