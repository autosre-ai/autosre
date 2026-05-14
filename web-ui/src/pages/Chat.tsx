import { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  History,
  AlertTriangle,
  Search,
  X,
  ChevronRight,
  Clock,
  Zap,
  Settings,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react';
import { Button, SeverityBadge, Card, CardContent } from '@/components/ui';
import { ChatMessage, TypingIndicator, InvestigationUpdate } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { cn, formatRelativeTime, generateId } from '@/lib/utils';
import { mockAlerts, mockInvestigations, mockChatSessions } from '@/data/mockData';
import type { ChatMessage as ChatMessageType, Alert, Investigation } from '@/types';

// Simulated AI responses for demo
const aiResponses = [
  `I'll investigate this alert right away. Let me start by checking the recent deployments and system metrics.

Based on my analysis, I found the following:

### Initial Findings

1. **Recent Deployment**: A deployment occurred 5 minutes before the latency spike
2. **Service Impact**: The checkout service is experiencing p99 latency > 5s
3. **Error Pattern**: Slow query warnings detected in logs

Let me dig deeper into the database queries...`,

  `After analyzing the logs, I identified the root cause:

\`\`\`sql
SELECT * FROM transactions WHERE user_id = ? AND status = 'pending'
\`\`\`

This query is missing an index on \`(user_id, status)\`, causing a full table scan under load.

### Recommended Actions

- **Short-term**: Roll back to v2.4.1 to restore service
- **Long-term**: Add the missing index: \`CREATE INDEX idx_transactions_user_status ON transactions(user_id, status);\`

Would you like me to initiate the rollback?`,

  `I'm checking the pod status across all replicas...

\`\`\`bash
kubectl get pods -n payments -l app=payment-gateway-api
\`\`\`

Results show all 3 pods are running but with elevated CPU usage. The new code path is significantly more resource-intensive.

I recommend scaling up to 5 replicas while we investigate further.`,
];

export function ChatPage() {
  const [searchParams] = useSearchParams();
  const alertId = searchParams.get('alert');
  const investigationId = searchParams.get('investigation');

  // Find related context
  const contextAlert = alertId ? mockAlerts.find((a) => a.id === alertId) : undefined;
  const contextInvestigation = investigationId
    ? mockInvestigations.find((i) => i.id === investigationId)
    : contextAlert?.investigationId
      ? mockInvestigations.find((i) => i.id === contextAlert.investigationId)
      : undefined;

  const [messages, setMessages] = useState<ChatMessageType[]>(() => {
    // Initialize with context-aware welcome message
    const welcomeMessage: ChatMessageType = {
      id: generateId(),
      role: 'assistant',
      content: contextAlert
        ? `I see you're investigating **${contextAlert.title}**. This is a ${contextAlert.severity} severity alert from ${contextAlert.service}.\n\nHow can I help you with this investigation? I can:\n- Analyze related logs and metrics\n- Check for recent deployments\n- Suggest remediation steps\n- Execute diagnostic commands`
        : `Hello! I'm your SRE Assistant. I can help you investigate alerts, diagnose issues, and suggest remediation actions.\n\n**Quick commands:**\n- Ask me to investigate any active alert\n- Run diagnostic queries on your services\n- Get recommendations for resolving incidents\n\nHow can I help you today?`,
      timestamp: new Date().toISOString(),
    };
    return [welcomeMessage];
  });

  const [isLoading, setIsLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showContext, setShowContext] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Simulate AI response
  const simulateResponse = useCallback(async (userMessage: string) => {
    setIsLoading(true);

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 1500 + Math.random() * 1500));

    const responseIndex = Math.floor(Math.random() * aiResponses.length);
    const aiMessage: ChatMessageType = {
      id: generateId(),
      role: 'assistant',
      content: aiResponses[responseIndex],
      timestamp: new Date().toISOString(),
      metadata: {
        toolName: 'kubectl',
        toolOutput: 'NAME                                READY   STATUS    RESTARTS   AGE\npayment-gateway-api-7f8d6b5c9-x2j4n   1/1     Running   0          35m\npayment-gateway-api-7f8d6b5c9-k9m2p   1/1     Running   0          35m\npayment-gateway-api-7f8d6b5c9-w8n3q   1/1     Running   0          35m',
      },
    };

    setMessages((prev) => [...prev, aiMessage]);
    setIsLoading(false);
  }, []);

  const handleSend = useCallback(
    (content: string) => {
      const userMessage: ChatMessageType = {
        id: generateId(),
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      simulateResponse(content);
    },
    [simulateResponse]
  );

  const handleStop = useCallback(() => {
    setIsLoading(false);
  }, []);

  const handleRetry = useCallback(() => {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMessage) {
      // Remove last assistant message and retry
      setMessages((prev) => {
        const lastAssistantIndex = prev.map((m) => m.role).lastIndexOf('assistant');
        if (lastAssistantIndex > 0) {
          return prev.slice(0, lastAssistantIndex);
        }
        return prev;
      });
      simulateResponse(lastUserMessage.content);
    }
  }, [messages, simulateResponse]);

  const handleNewChat = useCallback(() => {
    setMessages([
      {
        id: generateId(),
        role: 'assistant',
        content: `Hello! I'm your SRE Assistant. How can I help you today?`,
        timestamp: new Date().toISOString(),
      },
    ]);
  }, []);

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Chat History Sidebar */}
      <div
        className={cn(
          'flex-shrink-0 w-64 bg-stone-900 border-r border-stone-800 flex flex-col transition-all duration-300 overflow-hidden',
          showHistory ? 'translate-x-0' : '-translate-x-full w-0 border-0'
        )}
      >
        <div className="p-4 border-b border-stone-800">
          <Button onClick={handleNewChat} className="w-full justify-start gap-2">
            <Plus className="w-4 h-4" />
            New Chat
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="px-2 py-1 text-xs font-medium text-stone-500 uppercase tracking-wider">
            Recent Chats
          </div>
          {mockChatSessions.map((session) => (
            <button
              key={session.id}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm text-stone-300 hover:bg-stone-800 transition-colors"
            >
              <MessageSquare className="w-4 h-4 text-stone-500 flex-shrink-0" />
              <span className="truncate">{session.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-stone-800 bg-stone-900/50">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="p-2 text-stone-400 hover:text-white hover:bg-stone-800 rounded-lg transition-colors"
            >
              {showHistory ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeft className="w-5 h-5" />}
            </button>
            <div>
              <h1 className="text-lg font-semibold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-forest" />
                SRE Assistant
              </h1>
              <p className="text-xs text-stone-500">AI-powered incident response</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowContext(!showContext)}
              className={cn(
                'p-2 rounded-lg transition-colors',
                showContext
                  ? 'text-forest bg-forest/10'
                  : 'text-stone-400 hover:text-white hover:bg-stone-800'
              )}
              title="Toggle context panel"
            >
              <Search className="w-5 h-5" />
            </button>
            <button className="p-2 text-stone-400 hover:text-white hover:bg-stone-800 rounded-lg transition-colors">
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex flex-1 min-h-0">
          {/* Chat Messages */}
          <div ref={chatContainerRef} className="flex-1 overflow-y-auto">
            <div className="max-w-3xl mx-auto">
              {messages.map((message, index) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  isLast={index === messages.length - 1 && message.role === 'assistant'}
                  onRetry={handleRetry}
                />
              ))}

              {/* Investigation updates when in context */}
              {contextInvestigation && messages.length === 1 && (
                <div className="px-4 py-2">
                  <InvestigationUpdate
                    status="running"
                    title="Investigation in progress"
                    description={`Analyzing ${contextInvestigation.steps.length} steps completed`}
                    timestamp={contextInvestigation.startedAt}
                  />
                </div>
              )}

              {isLoading && <TypingIndicator />}
              <div ref={messagesEndRef} className="h-4" />
            </div>
          </div>

          {/* Context Panel */}
          {showContext && (contextAlert || contextInvestigation) && (
            <div className="w-80 border-l border-stone-800 bg-stone-900/50 overflow-y-auto flex-shrink-0">
              <div className="p-4 border-b border-stone-800">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-white">Context</h3>
                  <button
                    onClick={() => setShowContext(false)}
                    className="p-1 text-stone-500 hover:text-white rounded"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="p-4 space-y-4">
                {/* Alert Context */}
                {contextAlert && (
                  <Card className="bg-stone-800/50 border-stone-700">
                    <CardContent className="py-3">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <SeverityBadge severity={contextAlert.severity} />
                          </div>
                          <h4 className="text-sm font-medium text-white truncate">
                            {contextAlert.title}
                          </h4>
                          <p className="text-xs text-stone-400 mt-1">
                            {contextAlert.service} • {formatRelativeTime(contextAlert.startsAt)}
                          </p>
                          <Link
                            to={`/alerts/${contextAlert.id}`}
                            className="inline-flex items-center gap-1 text-xs text-forest hover:text-forest-light mt-2"
                          >
                            View details
                            <ChevronRight className="w-3 h-3" />
                          </Link>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Investigation Context */}
                {contextInvestigation && (
                  <Card className="bg-stone-800/50 border-stone-700">
                    <CardContent className="py-3">
                      <div className="flex items-start gap-3">
                        <Search className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium text-white">Active Investigation</h4>
                          <p className="text-xs text-stone-400 mt-1">
                            {contextInvestigation.steps.length} steps •{' '}
                            {formatRelativeTime(contextInvestigation.startedAt)}
                          </p>

                          {/* Recent steps */}
                          <div className="mt-3 space-y-2">
                            {contextInvestigation.steps.slice(-3).map((step) => (
                              <div
                                key={step.id}
                                className="flex items-start gap-2 text-xs"
                              >
                                <div
                                  className={cn(
                                    'w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0',
                                    step.status === 'success' && 'bg-green-400',
                                    step.status === 'pending' && 'bg-yellow-400',
                                    step.status === 'running' && 'bg-blue-400 animate-pulse',
                                    step.status === 'error' && 'bg-red-400'
                                  )}
                                />
                                <span className="text-stone-400 truncate">{step.title}</span>
                              </div>
                            ))}
                          </div>

                          <Link
                            to={`/investigations/${contextInvestigation.id}`}
                            className="inline-flex items-center gap-1 text-xs text-forest hover:text-forest-light mt-3"
                          >
                            View investigation
                            <ChevronRight className="w-3 h-3" />
                          </Link>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Quick Stats */}
                <div className="pt-2">
                  <h4 className="text-xs font-medium text-stone-500 uppercase tracking-wider mb-2">
                    Quick Stats
                  </h4>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 rounded-lg bg-stone-800/50 text-center">
                      <div className="text-lg font-bold text-white">
                        {mockAlerts.filter((a) => a.status === 'firing').length}
                      </div>
                      <div className="text-xs text-stone-500">Active Alerts</div>
                    </div>
                    <div className="p-2 rounded-lg bg-stone-800/50 text-center">
                      <div className="text-lg font-bold text-white">
                        {mockInvestigations.filter((i) => i.status === 'in_progress').length}
                      </div>
                      <div className="text-xs text-stone-500">Investigations</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <ChatInput onSend={handleSend} onStop={handleStop} isLoading={isLoading} />
      </div>
    </div>
  );
}
