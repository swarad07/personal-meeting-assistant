export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ---------------------------------------------------------------------------
// Meetings
// ---------------------------------------------------------------------------

export interface Attendee {
  id: string;
  name: string;
  email: string | null;
  role: string | null;
}

export interface Meeting {
  id: string;
  granola_id: string | null;
  title: string;
  date: string;
  duration: number | null;
  summary: string | null;
  synced_at: string | null;
  sync_source: "mcp" | "cache" | null;
  attendees: Attendee[];
  action_items_count: number;
}

export interface TranscriptChunk {
  id: string;
  chunk_index: number;
  speaker: string | null;
  content: string;
  start_time: number | null;
  end_time: number | null;
}

export interface MeetingDetail extends Meeting {
  raw_notes: string | null;
  enhanced_notes: string | null;
  next_call_brief: string | null;
  transcript_chunks: TranscriptChunk[];
  action_items: ActionItem[];
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchRequest {
  query: string;
  filters?: {
    date_from?: string;
    date_to?: string;
    attendees?: string[];
    topics?: string[];
  };
  page?: number;
  page_size?: number;
}

export interface SearchResultItem {
  meeting_id: string;
  title: string;
  date: string;
  snippet: string;
  score: number;
  source: "fulltext" | "semantic" | "graph";
}

export interface SearchResponse {
  results: SearchResultItem[];
  synthesis: string | null;
  total: number;
}

// ---------------------------------------------------------------------------
// Profiles
// ---------------------------------------------------------------------------

export interface Profile {
  id: string;
  type: "self" | "contact" | "org";
  name: string;
  email: string | null;
  bio: string | null;
  traits: Record<string, unknown> | null;
  aliases: string[] | null;
  meeting_count: number;
}

export interface ProfileDetail extends Profile {
  notes: string | null;
  learning_log: Array<Record<string, unknown>>;
  recent_meetings: Array<{ id: string; title: string; date: string; summary: string | null }>;
  action_items: Array<{ id: string; description: string; status: string; meeting_id: string }>;
}

// ---------------------------------------------------------------------------
// Action Items
// ---------------------------------------------------------------------------

export interface ActionItem {
  id: string;
  meeting_id: string;
  assignee: string;
  description: string;
  status: "open" | "done" | "dismissed";
  due_date: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export interface AgentInfo {
  name: string;
  description: string;
  pipeline: "sync" | "briefing" | "on_demand";
  dependencies: string[];
  required_mcp_providers: string[];
  total_runs: number;
  success_rate: number | null;
  can_trigger: boolean;
  last_run: AgentRun | null;
  recent_runs?: AgentRun[];
}

export interface AgentRun {
  id: string;
  pipeline: string;
  agent_name: string;
  trigger: string;
  status: string;
  meetings_processed: number;
  entities_extracted: number;
  errors_count: number;
  tokens_used: number;
  duration_ms: number;
  started_at: string;
  completed_at: string | null;
  result_summary: string | null;
}

// ---------------------------------------------------------------------------
// MCP Connections
// ---------------------------------------------------------------------------

export interface MCPConnection {
  provider: string;
  description: string;
  auth_type: string;
  status: string;
  last_sync: string | null;
  last_error: string | null;
}

// ---------------------------------------------------------------------------
// Briefings
// ---------------------------------------------------------------------------

export interface Briefing {
  id: string;
  meeting_id: string | null;
  calendar_event_id: string | null;
  title: string;
  content: string;
  topics: string[] | null;
  attendee_context: unknown;
  action_items_context: unknown;
  created_at: string | null;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

export interface CalendarEventAttendee {
  email: string | null;
  name: string | null;
  response_status: string | null;
}

export interface CalendarEvent {
  event_id: string;
  title: string;
  start: string;
  end: string;
  description: string | null;
  location: string | null;
  attendees: CalendarEventAttendee[];
  html_link: string | null;
  briefing?: {
    id: string;
    content: string;
    topics: string[] | null;
  };
}

// ---------------------------------------------------------------------------
// System Status
// ---------------------------------------------------------------------------

export interface SystemStatus {
  providers: Array<{
    name: string;
    status: "healthy" | "degraded" | "disconnected";
    auth_type: string;
    source?: "mcp" | "cache";
  }>;
  active_runs: Array<{
    id: string;
    pipeline: string;
    agent_name: string;
    started_at: string;
    elapsed_minutes: number;
  }>;
  recent_runs: Array<{
    id: string;
    pipeline: string;
    agent_name: string;
    status: string;
    started_at: string;
    completed_at: string | null;
    duration_ms: number | null;
    meetings_processed: number;
    errors_count: number;
  }>;
  scheduler: {
    next_sync: string | null;
    next_briefing: string | null;
  };
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Relationships (graph)
// ---------------------------------------------------------------------------

export interface GraphNode {
  id: string;
  label: string;
  type: "person" | "organization" | "topic" | "project" | "meeting";
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
