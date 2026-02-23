import type {
  PaginatedResponse,
  Meeting,
  MeetingDetail,
  SearchRequest,
  SearchResponse,
  Profile,
  ProfileDetail,
  ActionItem,
  AgentInfo,
  AgentRun,
  MCPConnection,
  Briefing,
  CalendarEvent,
  GraphData,
  SystemStatus,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res.json();
}

export const api = {
  health: () => fetchAPI<{ status: string }>("/api/health"),
  status: () => fetchAPI<SystemStatus>("/api/status/"),
  cancelRun: (runId: string) =>
    fetchAPI<{ status: string; run_id: string }>(
      `/api/status/cancel-run/${runId}`,
      { method: "POST" },
    ),

  meetings: {
    list: (page = 1, pageSize = 20) =>
      fetchAPI<PaginatedResponse<Meeting>>(
        `/api/meetings/?page=${page}&page_size=${pageSize}`,
      ),
    get: (id: string) => fetchAPI<MeetingDetail>(`/api/meetings/${id}`),
    resync: (id: string) =>
      fetchAPI<{ status: string; has_notes?: boolean; has_summary?: boolean; transcript_chunks?: number }>(
        `/api/meetings/${id}/resync`,
        { method: "POST" },
      ),
    generateSummary: (id: string) =>
      fetchAPI<{ status: string; summary?: string; reason?: string }>(
        `/api/meetings/${id}/generate-summary`,
        { method: "POST" },
      ),
    generateBrief: (id: string) =>
      fetchAPI<{ status: string; brief?: string; meeting_title?: string }>(
        `/api/meetings/${id}/generate-brief`,
        { method: "POST" },
      ),
    sync: () =>
      fetchAPI<{ message: string; result: Record<string, unknown> }>(
        "/api/meetings/sync",
        { method: "POST" },
      ),
    fullPipeline: () =>
      fetchAPI<{ message: string; results: Record<string, unknown> }>(
        "/api/meetings/sync/full",
        { method: "POST" },
      ),
  },

  search: {
    query: (req: SearchRequest) =>
      fetchAPI<SearchResponse>("/api/search", {
        method: "POST",
        body: JSON.stringify(req),
      }),
  },

  relationships: {
    graph: (opts?: { entityId?: string; type?: string; limit?: number }) => {
      const params = new URLSearchParams();
      if (opts?.entityId) params.set("entity_id", opts.entityId);
      if (opts?.type) params.set("type", opts.type);
      params.set("limit", String(opts?.limit ?? 200));
      return fetchAPI<GraphData>(`/api/relationships?${params.toString()}`);
    },
    entity: (entityId: string) =>
      fetchAPI<{
        entity: { id: string; label: string; type: string; properties: Record<string, unknown> } | null;
        neighbors: Array<{ id: string; label: string; type: string; properties: Record<string, unknown> }>;
        edges: Array<{ id: string; source: string; target: string; type: string; properties: Record<string, unknown> }>;
      }>(`/api/relationships/${encodeURIComponent(entityId)}`),
    search: (q: string) =>
      fetchAPI<Array<{ id: string; name: string; type: string }>>(
        `/api/relationships/search?q=${encodeURIComponent(q)}`,
      ),
    meetings: (entityId: string) =>
      fetchAPI<{ entity_id: string; meeting_ids: string[] }>(
        `/api/relationships/${encodeURIComponent(entityId)}/meetings`,
      ),
  },

  profiles: {
    list: (page = 1, pageSize = 50) =>
      fetchAPI<PaginatedResponse<Profile>>(
        `/api/profiles/?page=${page}&page_size=${pageSize}`,
      ),
    me: () => fetchAPI<ProfileDetail>("/api/profiles/me"),
    get: (id: string) => fetchAPI<ProfileDetail>(`/api/profiles/${id}`),
    update: (id: string, data: { name?: string; bio?: string; notes?: string }) =>
      fetchAPI<ProfileDetail>(`/api/profiles/${id === "me" ? "me" : id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    generateBio: (id: string) =>
      fetchAPI<{ status: string; bio?: string; reason?: string }>(
        `/api/profiles/${id}/generate-bio`,
        { method: "POST" },
      ),
  },

  calendar: {
    events: (days = 7) =>
      fetchAPI<{ events: CalendarEvent[]; count: number }>(
        `/api/calendar/events?days=${days}`,
      ),
    event: (eventId: string) =>
      fetchAPI<CalendarEvent>(`/api/calendar/events/${eventId}`),
    sync: () =>
      fetchAPI<{ message: string }>("/api/calendar/sync", { method: "POST" }),
  },

  actionItems: {
    list: (status?: string, assignee?: string, page = 1, pageSize = 20) => {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (status) params.set("status", status);
      if (assignee) params.set("assignee", assignee);
      return fetchAPI<PaginatedResponse<ActionItem>>(
        `/api/action-items/?${params.toString()}`,
      );
    },
    update: (id: string, data: { status: string }) =>
      fetchAPI<ActionItem>(`/api/action-items/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },

  briefings: {
    list: (page = 1, pageSize = 10) =>
      fetchAPI<PaginatedResponse<Briefing>>(
        `/api/briefings/?page=${page}&page_size=${pageSize}`,
      ),
    get: (briefingId: string) =>
      fetchAPI<Briefing>(`/api/briefings/${briefingId}`),
    byEvent: (calendarEventId: string) =>
      fetchAPI<Briefing>(`/api/briefings/event/${calendarEventId}`),
    generate: () =>
      fetchAPI<{ message: string }>("/api/briefings/generate", {
        method: "POST",
      }),
  },

  agents: {
    list: () => fetchAPI<AgentInfo[]>("/api/agents/"),
    get: (name: string) => fetchAPI<AgentInfo>(`/api/agents/${name}`),
    runs: (name: string, page = 1, pageSize = 20) =>
      fetchAPI<PaginatedResponse<AgentRun>>(
        `/api/agents/${name}/runs?page=${page}&page_size=${pageSize}`,
      ),
    trigger: (name: string) =>
      fetchAPI<{ message: string; agent_name: string }>(
        `/api/agents/${name}/trigger`,
        { method: "POST" },
      ),
  },

  connections: {
    list: () => fetchAPI<MCPConnection[]>("/api/connections/"),
    authUrl: (provider: string, redirectUri?: string) =>
      fetchAPI<{ auth_url: string | null }>(`/api/connections/${provider}/auth-url`, {
        method: "POST",
        body: JSON.stringify({ redirect_uri: redirectUri || "http://localhost:3000/settings/connections/callback" }),
      }),
    connect: (provider: string, tokens: Record<string, unknown>) =>
      fetchAPI<{ provider: string; connected: boolean }>(`/api/connections/${provider}/connect`, {
        method: "POST",
        body: JSON.stringify({ tokens }),
      }),
    callback: (provider: string, code: string, redirectUri: string) =>
      fetchAPI<{ provider: string; connected: boolean }>(`/api/connections/${provider}/callback`, {
        method: "POST",
        body: JSON.stringify({ code, redirect_uri: redirectUri }),
      }),
    disconnect: (provider: string) =>
      fetchAPI<{ provider: string; status: string }>(`/api/connections/${provider}`, {
        method: "DELETE",
      }),
    health: (provider: string) =>
      fetchAPI<{ provider: string; status: string }>(`/api/connections/${provider}/health`),
  },
};
