import { forwardRef, useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Mic, StopCircle, Sparkles, Terminal, AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

interface QuickAction {
  label: string;
  icon: typeof Sparkles;
  prompt: string;
  color: string;
}

const quickActions: QuickAction[] = [
  {
    label: 'Investigate Alert',
    icon: AlertTriangle,
    prompt: 'Investigate the current alert and identify the root cause',
    color: 'text-red-400 bg-red-500/10 hover:bg-red-500/20',
  },
  {
    label: 'Run Diagnostics',
    icon: Terminal,
    prompt: 'Run diagnostics on the affected service',
    color: 'text-blue-400 bg-blue-500/10 hover:bg-blue-500/20',
  },
  {
    label: 'Suggest Fix',
    icon: Sparkles,
    prompt: 'Based on your analysis, suggest a remediation plan',
    color: 'text-forest bg-forest/10 hover:bg-forest/20',
  },
  {
    label: 'Rollback',
    icon: RotateCcw,
    prompt: 'Should we rollback the recent deployment?',
    color: 'text-orange-400 bg-orange-500/10 hover:bg-orange-500/20',
  },
];

export const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(
  ({ onSend, onStop, disabled, isLoading, placeholder = 'Ask SRE Assistant...', className }, ref) => {
    const [message, setMessage] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const combinedRef = ref || textareaRef;

    // Auto-resize textarea
    useEffect(() => {
      const textarea = typeof combinedRef === 'function' ? textareaRef.current : combinedRef?.current;
      if (textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
      }
    }, [message, combinedRef]);

    const handleSubmit = () => {
      const trimmed = message.trim();
      if (trimmed && !disabled && !isLoading) {
        onSend(trimmed);
        setMessage('');
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    };

    const handleQuickAction = (action: QuickAction) => {
      onSend(action.prompt);
    };

    return (
      <div className={cn('border-t border-stone-800 bg-stone-900', className)}>
        {/* Quick Actions */}
        <div className="px-4 pt-3 pb-2 flex gap-2 overflow-x-auto scrollbar-hide">
          {quickActions.map((action) => (
            <button
              key={action.label}
              onClick={() => handleQuickAction(action)}
              disabled={disabled || isLoading}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                action.color,
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <action.icon className="w-3.5 h-3.5" />
              {action.label}
            </button>
          ))}
        </div>

        {/* Input Area */}
        <div className="px-4 pb-4">
          <div className="relative flex items-end gap-2 bg-stone-800 rounded-xl border border-stone-700 focus-within:border-forest transition-colors">
            {/* Attachment button */}
            <button
              type="button"
              className="p-3 text-stone-500 hover:text-stone-300 transition-colors self-end"
              disabled={disabled || isLoading}
            >
              <Paperclip className="w-5 h-5" />
            </button>

            {/* Textarea */}
            <textarea
              ref={combinedRef as React.RefObject<HTMLTextAreaElement>}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled || isLoading}
              rows={1}
              className={cn(
                'flex-1 py-3 bg-transparent resize-none outline-none',
                'text-white placeholder:text-stone-500',
                'min-h-[48px] max-h-[200px]',
                'disabled:opacity-50'
              )}
            />

            {/* Voice button */}
            <button
              type="button"
              className="p-3 text-stone-500 hover:text-stone-300 transition-colors self-end hidden sm:block"
              disabled={disabled || isLoading}
            >
              <Mic className="w-5 h-5" />
            </button>

            {/* Send/Stop button */}
            {isLoading ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={onStop}
                className="m-2 self-end text-red-400 hover:text-red-300 hover:bg-red-500/10"
              >
                <StopCircle className="w-5 h-5" />
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={handleSubmit}
                disabled={!message.trim() || disabled}
                className="m-2 self-end"
              >
                <Send className="w-4 h-4" />
              </Button>
            )}
          </div>

          {/* Disclaimer */}
          <p className="text-xs text-stone-600 text-center mt-2">
            SRE Assistant can make mistakes. Always verify before taking actions.
          </p>
        </div>
      </div>
    );
  }
);

ChatInput.displayName = 'ChatInput';
