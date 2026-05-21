// AutoSRE API Client

import type {
  Investigation,
  InvestigationRequest,
  InvestigationListItem,
  Episode,
  Memory,
  Skill,
  TeamConfig,
  LLMConfig,
  SSEEvent,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "APIError";
  }
}

async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new APIError(response.status, error || response.statusText);
  }

  return response.json();
}

// Investigation API
export const investigationAPI = {
  list: (): Promise<InvestigationListItem[]> =>
    fetchAPI("/api/investigations"),

  get: (id: string): Promise<Investigation> =>
    fetchAPI(`/api/investigations/${id}`),

  create: (data: InvestigationRequest): Promise<Investigation> =>
    fetchAPI("/api/investigations", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  cancel: (id: string): Promise<void> =>
    fetchAPI(`/api/investigations/${id}/cancel`, {
      method: "POST",
    }),

  // SSE stream for real-time updates
  stream: (
    id: string,
    onEvent: (event: SSEEvent) => void,
    onError?: (error: Error) => void
  ): (() => void) => {
    const eventSource = new EventSource(
      `${API_BASE}/api/investigations/${id}/stream`
    );

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as SSEEvent;
        onEvent(data);
      } catch (e) {
        console.error("Failed to parse SSE event:", e);
      }
    };

    eventSource.onerror = (error) => {
      console.error("SSE error:", error);
      onError?.(new Error("Connection lost"));
      eventSource.close();
    };

    return () => eventSource.close();
  },

  // Start investigation with streaming
  startStream: async function* (
    data: InvestigationRequest
  ): AsyncGenerator<SSEEvent> {
    const response = await fetch(`${API_BASE}/api/investigations/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!response.ok || !response.body) {
      throw new APIError(response.status, "Failed to start investigation");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6)) as SSEEvent;
            yield data;
          } catch {
            // Skip malformed events
          }
        }
      }
    }
  },
};

// Memory API
export const memoryAPI = {
  getMemory: (): Promise<Memory> => fetchAPI("/api/memory"),

  getEpisodes: (limit?: number): Promise<Episode[]> =>
    fetchAPI(`/api/memory/episodes${limit ? `?limit=${limit}` : ""}`),

  getEpisode: (id: string): Promise<Episode> =>
    fetchAPI(`/api/memory/episodes/${id}`),

  searchSimilar: (query: string, limit = 5): Promise<Episode[]> =>
    fetchAPI(
      `/api/memory/search?q=${encodeURIComponent(query)}&limit=${limit}`
    ),

  deleteEpisode: (id: string): Promise<void> =>
    fetchAPI(`/api/memory/episodes/${id}`, { method: "DELETE" }),
};

// Skills API
export const skillsAPI = {
  list: (): Promise<Skill[]> => fetchAPI("/api/skills"),

  get: (id: string): Promise<Skill> => fetchAPI(`/api/skills/${id}`),

  toggle: (id: string, enabled: boolean): Promise<Skill> =>
    fetchAPI(`/api/skills/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }),

  test: (
    id: string,
    params: Record<string, unknown>
  ): Promise<{ success: boolean; output: unknown }> =>
    fetchAPI(`/api/skills/${id}/test`, {
      method: "POST",
      body: JSON.stringify(params),
    }),
};

// Config API
export const configAPI = {
  getTeam: (): Promise<TeamConfig> => fetchAPI("/api/config/team"),

  updateTeam: (config: Partial<TeamConfig>): Promise<TeamConfig> =>
    fetchAPI("/api/config/team", {
      method: "PATCH",
      body: JSON.stringify(config),
    }),

  getLLM: (): Promise<LLMConfig> => fetchAPI("/api/config/llm"),

  updateLLM: (config: Partial<LLMConfig>): Promise<LLMConfig> =>
    fetchAPI("/api/config/llm", {
      method: "PATCH",
      body: JSON.stringify(config),
    }),
};

// Health check
export const healthCheck = (): Promise<{ status: string; version: string }> =>
  fetchAPI("/api/health");
