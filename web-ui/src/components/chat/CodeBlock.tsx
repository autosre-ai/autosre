import { useState } from 'react';
import { Check, Copy, Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  className?: string;
}

// Simple syntax highlighting for common SRE languages
function highlightSyntax(code: string, language: string): string {
  // Keywords for different languages
  const keywords: Record<string, string[]> = {
    bash: ['if', 'then', 'else', 'fi', 'for', 'do', 'done', 'while', 'case', 'esac', 'function', 'return', 'exit', 'export', 'source'],
    sql: ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'ON', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'OFFSET', 'INTO', 'VALUES', 'SET', 'NULL', 'NOT', 'IN', 'LIKE', 'AS', 'TABLE', 'INDEX', 'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES'],
    yaml: ['true', 'false', 'null', 'yes', 'no'],
    json: ['true', 'false', 'null'],
    javascript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'extends', 'import', 'export', 'default', 'from', 'async', 'await', 'try', 'catch', 'throw', 'new', 'this', 'typeof', 'instanceof'],
    python: ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'return', 'import', 'from', 'as', 'try', 'except', 'finally', 'raise', 'with', 'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is', 'lambda', 'async', 'await'],
  };

  // Just return the code for now - we could add actual highlighting
  // For production, use a library like prism-react-renderer
  return code;
}

export function CodeBlock({ code, language = 'bash', filename, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Detect language from filename if not specified
  const detectedLanguage = language || detectLanguage(filename);

  return (
    <div className={cn('group relative rounded-lg overflow-hidden bg-stone-950', className)}>
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-stone-900/80 border-b border-stone-800">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-stone-500" />
          <span className="text-xs text-stone-400 font-mono">
            {filename || detectedLanguage}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-all',
            'text-stone-400 hover:text-white hover:bg-stone-800',
            copied && 'text-green-400'
          )}
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5" />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code content */}
      <div className="overflow-x-auto">
        <pre className="p-4 text-sm leading-relaxed">
          <code className={cn('font-mono text-stone-300', `language-${detectedLanguage}`)}>
            {code}
          </code>
        </pre>
      </div>
    </div>
  );
}

function detectLanguage(filename?: string): string {
  if (!filename) return 'bash';
  
  const ext = filename.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    sh: 'bash',
    bash: 'bash',
    zsh: 'bash',
    sql: 'sql',
    yaml: 'yaml',
    yml: 'yaml',
    json: 'json',
    js: 'javascript',
    ts: 'typescript',
    py: 'python',
    rb: 'ruby',
    go: 'go',
    rs: 'rust',
    tf: 'terraform',
    hcl: 'terraform',
  };
  
  return langMap[ext || ''] || 'bash';
}

// Inline code component for use in markdown
export function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="px-1.5 py-0.5 rounded bg-stone-800 text-forest-light font-mono text-sm">
      {children}
    </code>
  );
}
