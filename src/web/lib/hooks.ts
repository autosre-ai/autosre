// AutoSRE Custom Hooks

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { create } from "zustand";
import { investigationAPI, memoryAPI, skillsAPI, configAPI } from "./api";
import type {
  Investigation,
  InvestigationRequest,
  SSEEvent,
  Message,
  Hypothesis,
  SkillExecution,
  Finding,
} from "./types";

// ============================================
// Zustand Stores
// ============================================

interface InvestigationState {
  currentInvestigation: Investigation | null;
  messages: Message[];
  activeSkills: SkillExecution[];
  hypotheses: Hypothesis[];
  findings: Finding[];
  isStreaming: boolean;
  setCurrentInvestigation: (inv: Investigation | null) => void;
  addMessage: (msg: Message) => void;
  clearMessages: () => void;
  addSkillExecution: (skill: SkillExecution) => void;
  updateSkillExecution: (id: string, updates: Partial<SkillExecution>) => void;
  addHypothesis: (h: Hypothesis) => void;
  updateHypothesis: (id: string, updates: Partial<Hypothesis>) => void;
  addFinding: (f: Finding) => void;
  setStreaming: (streaming: boolean) => void;
  reset: () => void;
}

export const useInvestigationStore = create<InvestigationState>((set) => ({
  currentInvestigation: null,
  messages: [],
  activeSkills: [],
  hypotheses: [],
  findings: [],
  isStreaming: false,
  setCurrentInvestigation: (inv) => set({ currentInvestigation: inv }),
  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),
  clearMessages: () => set({ messages: [] }),
  addSkillExecution: (skill) =>
    set((state) => ({ activeSkills: [...state.activeSkills, skill] })),
  updateSkillExecution: (id, updates) =>
    set((state) => ({
      activeSkills: state.activeSkills.map((s) =>
        s.id === id ? { ...s, ...updates } : s
      ),
    })),
  addHypothesis: (h) =>
    set((state) => ({ hypotheses: [...state.hypotheses, h] })),
  updateHypothesis: (id, updates) =>
    set((state) => ({
      hypotheses: state.hypotheses.map((h) =>
        h.id === id ? { ...h, ...updates } : h
      ),
    })),
  addFinding: (f) => set((state) => ({ findings: [...state.findings, f] })),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  reset: () =>
    set({
      currentInvestigation: null,
      messages: [],
      activeSkills: [],
      hypotheses: [],
      findings: [],
      isStreaming: false,
    }),
}));

// ============================================
// Query Hooks
// ============================================

export function useInvestigations() {
  return useQuery({
    queryKey: ["investigations"],
    queryFn: investigationAPI.list,
  });
}

export function useInvestigation(id: string) {
  return useQuery({
    queryKey: ["investigation", id],
    queryFn: () => investigationAPI.get(id),
    enabled: !!id,
  });
}

export function useMemory() {
  return useQuery({
    queryKey: ["memory"],
    queryFn: memoryAPI.getMemory,
  });
}

export function useEpisodes(limit?: number) {
  return useQuery({
    queryKey: ["episodes", limit],
    queryFn: () => memoryAPI.getEpisodes(limit),
  });
}

export function useSkills() {
  return useQuery({
    queryKey: ["skills"],
    queryFn: skillsAPI.list,
  });
}

export function useTeamConfig() {
  return useQuery({
    queryKey: ["config", "team"],
    queryFn: configAPI.getTeam,
  });
}

export function useLLMConfig() {
  return useQuery({
    queryKey: ["config", "llm"],
    queryFn: configAPI.getLLM,
  });
}

// ============================================
// Mutation Hooks
// ============================================

export function useStartInvestigation() {
  const queryClient = useQueryClient();
  const store = useInvestigationStore();

  return useMutation({
    mutationFn: async (request: InvestigationRequest) => {
      store.reset();
      store.setStreaming(true);

      try {
        for await (const event of investigationAPI.startStream(request)) {
          handleSSEEvent(event, store);
        }
      } finally {
        store.setStreaming(false);
      }

      return store.currentInvestigation;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
    },
  });
}

export function useToggleSkill() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      skillsAPI.toggle(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useUpdateTeamConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: configAPI.updateTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config", "team"] });
    },
  });
}

export function useUpdateLLMConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: configAPI.updateLLM,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["config", "llm"] });
    },
  });
}

export function useSearchEpisodes() {
  const [results, setResults] = useState<Awaited<
    ReturnType<typeof memoryAPI.searchSimilar>
  > | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const search = useCallback(async (query: string, limit = 5) => {
    setIsSearching(true);
    try {
      const episodes = await memoryAPI.searchSimilar(query, limit);
      setResults(episodes);
    } finally {
      setIsSearching(false);
    }
  }, []);

  return { search, results, isSearching, clearResults: () => setResults(null) };
}

// ============================================
// SSE Stream Hook
// ============================================

export function useInvestigationStream(investigationId: string | null) {
  const store = useInvestigationStore();
  const closeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!investigationId) return;

    closeRef.current = investigationAPI.stream(
      investigationId,
      (event) => handleSSEEvent(event, store),
      (error) => {
        console.error("Stream error:", error);
        store.setStreaming(false);
      }
    );

    store.setStreaming(true);

    return () => {
      closeRef.current?.();
      store.setStreaming(false);
    };
  }, [investigationId, store]);
}

// Helper to handle SSE events
function handleSSEEvent(event: SSEEvent, store: InvestigationState) {
  switch (event.type) {
    case "message":
      store.addMessage(event.data as Message);
      break;

    case "skill_start":
      store.addSkillExecution(event.data as SkillExecution);
      break;

    case "skill_end": {
      const skill = event.data as SkillExecution;
      store.updateSkillExecution(skill.id, skill);
      break;
    }

    case "hypothesis":
      store.addHypothesis(event.data as Hypothesis);
      break;

    case "finding":
      store.addFinding(event.data as Finding);
      break;

    case "error":
      store.addMessage({
        id: crypto.randomUUID(),
        role: "system",
        content: `Error: ${event.data}`,
        timestamp: new Date().toISOString(),
      });
      break;

    case "done":
      store.setStreaming(false);
      if (event.data) {
        store.setCurrentInvestigation(event.data as Investigation);
      }
      break;
  }
}

// ============================================
// UI Utility Hooks
// ============================================

export function useAutoScroll(dependency: unknown) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [dependency]);

  return ref;
}

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
