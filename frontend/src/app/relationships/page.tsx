"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import { api } from "@/lib/api-client";
import type { GraphNode, GraphEdge } from "@/lib/types";
import {
  Search,
  X,
  User,
  Building2,
  Hash,
  MessageSquare,
  ArrowRight,
  Network,
  LayoutList,
  CalendarDays,
  Users,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { format, parseISO } from "date-fns";
import { getInitials } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NODE_GRADIENTS: Record<string, string> = {
  person: "linear-gradient(135deg, #6366f1, #818cf8)",
  organization: "linear-gradient(135deg, #8b5cf6, #a78bfa)",
  topic: "linear-gradient(135deg, #06b6d4, #22d3ee)",
  project: "linear-gradient(135deg, #f59e0b, #fbbf24)",
  meeting: "linear-gradient(135deg, #64748b, #94a3b8)",
};

const TYPE_ICONS: Record<string, typeof User> = {
  person: User,
  organization: Building2,
  topic: Hash,
};

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg, #6366f1, #818cf8)",
  "linear-gradient(135deg, #8b5cf6, #a78bfa)",
  "linear-gradient(135deg, #06b6d4, #22d3ee)",
  "linear-gradient(135deg, #f59e0b, #fbbf24)",
  "linear-gradient(135deg, #ec4899, #f472b6)",
  "linear-gradient(135deg, #10b981, #34d399)",
];

// ---------------------------------------------------------------------------
// Mini-graph layout helper
// ---------------------------------------------------------------------------

interface ForceNode extends SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
}

function computeMiniLayout(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
  width: number,
  height: number,
): { flowNodes: Node[]; flowEdges: Edge[] } {
  if (!graphNodes.length) return { flowNodes: [], flowEdges: [] };

  const simNodes: ForceNode[] = graphNodes.map((n) => ({
    id: n.id,
    label: n.label,
    type: n.type,
    x: width / 2 + (Math.random() - 0.5) * 200,
    y: height / 2 + (Math.random() - 0.5) * 200,
  }));

  const nodeIds = new Set(simNodes.map((n) => n.id));
  const simLinks: SimulationLinkDatum<ForceNode>[] = graphEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({ source: e.source, target: e.target }));

  const sim = forceSimulation(simNodes)
    .force("charge", forceManyBody().strength(-200))
    .force(
      "link",
      forceLink<ForceNode, SimulationLinkDatum<ForceNode>>(simLinks)
        .id((d) => d.id)
        .distance(100),
    )
    .force("center", forceCenter(width / 2, height / 2))
    .force("collision", forceCollide(40))
    .stop();

  for (let i = 0; i < 150; i++) sim.tick();

  const flowNodes: Node[] = simNodes.map((n) => ({
    id: n.id,
    type: "default",
    position: { x: n.x ?? 0, y: n.y ?? 0 },
    data: { label: n.label || n.id },
    style: {
      background: NODE_GRADIENTS[n.type] || NODE_GRADIENTS.meeting,
      color: "#fff",
      border: "2px solid rgba(255,255,255,0.2)",
      borderRadius: "14px",
      padding: "6px 14px",
      fontSize: "11px",
      fontWeight: 600,
      textAlign: "center" as const,
      cursor: "pointer",
      boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
    },
  }));

  const flowEdges: Edge[] = graphEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "default",
      style: {
        stroke: e.type === "KNOWS" ? "#a5b4fc" : "#cbd5e1",
        strokeWidth: Math.min(4, Math.max(1, (e.properties?.strength as number) ?? 1)),
        strokeDasharray: e.type === "KNOWS" ? undefined : "5 3",
      },
    }));

  return { flowNodes, flowEdges };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EmptyState({
  searchQuery,
  onSearch,
  onCategoryClick,
}: {
  searchQuery: string;
  onSearch: (q: string) => void;
  onCategoryClick: (type: string) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-20 text-center">
      <div className="relative mb-8">
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl gradient-bg shadow-xl shadow-accent-500/20">
          <Network size={36} className="text-white" />
        </div>
      </div>
      <h1 className="text-2xl font-bold tracking-tight text-text-primary mb-2">
        Relationship Explorer
      </h1>
      <p className="text-sm text-text-muted max-w-md mb-8">
        Search for a person, topic, or organization to explore their connections,
        shared meetings, and discussion history.
      </p>

      <div className="relative w-full max-w-lg mb-6">
        <Search
          size={18}
          className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted"
        />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search for a person, topic, or organization..."
          className="w-full rounded-2xl border border-border bg-surface py-3.5 pl-11 pr-10 text-sm text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_4px_rgba(99,102,241,0.1)] placeholder:text-text-muted transition-all"
          autoFocus
        />
        {searchQuery && (
          <button
            onClick={() => onSearch("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-text-muted mr-1">Quick:</span>
        {[
          { type: "person", label: "People", Icon: User },
          { type: "topic", label: "Topics", Icon: Hash },
          { type: "organization", label: "Orgs", Icon: Building2 },
        ].map(({ type, label, Icon }) => (
          <button
            key={type}
            onClick={() => onCategoryClick(type)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium border border-border text-text-secondary hover:bg-surface-overlay hover:border-accent-300 transition-all"
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ConnectionCard({
  neighbor,
  index,
  onSelect,
}: {
  neighbor: { id: string; label: string; type: string; properties: Record<string, unknown> };
  index: number;
  onSelect: (id: string) => void;
}) {
  const Icon = TYPE_ICONS[neighbor.type] ?? User;
  const mc = (neighbor.properties?.meeting_count as number) ?? 0;

  return (
    <button
      onClick={() => onSelect(neighbor.id)}
      className="flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-surface-overlay/60 transition-all min-w-[90px] group"
    >
      <div
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white text-xs font-bold shadow-md"
        style={{ background: AVATAR_GRADIENTS[index % AVATAR_GRADIENTS.length] }}
      >
        {neighbor.type === "person" ? (
          getInitials(neighbor.label)
        ) : (
          <Icon size={16} />
        )}
      </div>
      <div className="text-center min-w-0">
        <p className="text-xs font-medium text-text-primary truncate max-w-[80px] group-hover:text-accent-600 transition-colors">
          {neighbor.label}
        </p>
        {mc > 0 && (
          <p className="text-[10px] text-text-muted">{mc} meetings</p>
        )}
      </div>
    </button>
  );
}

function MeetingRow({
  meeting,
}: {
  meeting: {
    id: string;
    title: string;
    date: string | null;
    summary_snippet: string | null;
    attendees: string[];
  };
}) {
  return (
    <Link
      href={`/meetings/${meeting.id}`}
      className="flex items-start gap-3 p-3 rounded-xl hover:bg-surface-overlay/50 transition-colors group"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600 mt-0.5">
        <MessageSquare size={16} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text-primary group-hover:text-accent-600 transition-colors truncate">
          {meeting.title}
        </p>
        <div className="flex items-center gap-3 mt-1 text-xs text-text-muted">
          {meeting.date && (
            <span className="flex items-center gap-1">
              <CalendarDays size={11} />
              {format(parseISO(meeting.date), "MMM d, yyyy")}
            </span>
          )}
          {meeting.attendees.length > 0 && (
            <span className="flex items-center gap-1">
              <Users size={11} />
              {meeting.attendees.length}
            </span>
          )}
        </div>
        {meeting.summary_snippet && (
          <p className="text-xs text-text-muted mt-1 line-clamp-2">
            {meeting.summary_snippet}
          </p>
        )}
      </div>
      <ArrowRight
        size={14}
        className="text-text-muted opacity-0 group-hover:opacity-100 mt-2 transition-opacity shrink-0"
      />
    </Link>
  );
}

function MiniGraph({
  nodes: graphNodes,
  edges: graphEdges,
  onNodeClick,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  const elements = useMemo(() => {
    const w = 600;
    const h = 400;
    return computeMiniLayout(graphNodes, graphEdges, w, h);
  }, [graphNodes, graphEdges]);

  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState(elements.flowNodes);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState(elements.flowEdges);

  useEffect(() => {
    setFlowNodes(elements.flowNodes);
    setFlowEdges(elements.flowEdges);
  }, [elements, setFlowNodes, setFlowEdges]);

  return (
    <div ref={containerRef} className="h-[400px] rounded-xl border border-border overflow-hidden bg-surface">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => onNodeClick(node.id)}
        fitView
        proOptions={{ hideAttribution: true }}
        minZoom={0.3}
        maxZoom={1.5}
      >
        <Background color="#e2e8f0" gap={20} />
        <Controls style={{ bottom: 8, left: 8 }} showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RelationshipsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"cards" | "graph">("cards");

  const { data: searchResults } = useQuery({
    queryKey: ["rel-search", searchQuery],
    queryFn: () => api.relationships.search(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const { data: entityDetail, isLoading: detailLoading } = useQuery({
    queryKey: ["rel-entity", selectedEntityId],
    queryFn: () => api.relationships.entity(selectedEntityId!),
    enabled: !!selectedEntityId,
  });

  const { data: meetingsDetail, isLoading: meetingsLoading } = useQuery({
    queryKey: ["rel-meetings-detail", selectedEntityId],
    queryFn: () => api.relationships.meetingsDetail(selectedEntityId!),
    enabled: !!selectedEntityId,
  });

  const entity = entityDetail?.entity;
  const neighbors = entityDetail?.neighbors ?? [];
  const edges = entityDetail?.edges ?? [];
  const meetings = meetingsDetail ?? [];

  const personNeighbors = neighbors.filter((n) => n.type === "person");
  const topicNeighbors = neighbors.filter((n) => n.type === "topic");
  const orgNeighbors = neighbors.filter((n) => n.type === "organization");

  const graphNodes: GraphNode[] = useMemo(() => {
    if (!entity) return [];
    const all: GraphNode[] = [
      { id: entity.id, label: entity.label, type: entity.type as GraphNode["type"], properties: entity.properties },
      ...neighbors.map((n) => ({
        id: n.id,
        label: n.label,
        type: n.type as GraphNode["type"],
        properties: n.properties,
      })),
    ];
    return all;
  }, [entity, neighbors]);

  const graphEdges: GraphEdge[] = useMemo(
    () =>
      edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        properties: e.properties,
      })),
    [edges],
  );

  const handleSelectEntity = useCallback((id: string) => {
    setSelectedEntityId(id);
    setSearchQuery("");
    setViewMode("cards");
  }, []);

  const handleCategoryClick = useCallback((type: string) => {
    setSearchQuery(type === "person" ? "a" : type === "topic" ? "a" : "a");
    // Trigger a broad search — the backend's CONTAINS filter is lenient
    setSearchQuery("");
    // Instead, we'll fetch top entities of this type
    setSelectedEntityId(null);
  }, []);

  const showSearchDropdown =
    searchQuery.length >= 2 && searchResults && searchResults.length > 0;

  return (
    <div className="min-h-full">
      {/* Top bar (always visible) */}
      <div className="border-b border-border bg-surface-raised px-6 py-4">
        <div className="flex items-center justify-between gap-4 max-w-5xl mx-auto">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text-primary">
              Relationships
            </h1>
            <p className="text-xs text-text-muted mt-0.5">
              Explore connections between people, topics, and organizations
            </p>
          </div>

        </div>

        {/* Inline search when entity is selected */}
        {selectedEntityId && (
          <div className="relative max-w-5xl mx-auto mt-3">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search for another person, topic, or organization..."
              className="w-full max-w-md rounded-xl border border-border bg-surface py-2 pl-9 pr-8 text-xs text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.1)] placeholder:text-text-muted transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              >
                <X size={14} />
              </button>
            )}
            {showSearchDropdown && (
              <SearchDropdown
                results={searchResults!}
                onSelect={handleSelectEntity}
              />
            )}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        {!selectedEntityId ? (
          <>
            <EmptyState
              searchQuery={searchQuery}
              onSearch={setSearchQuery}
              onCategoryClick={handleCategoryClick}
            />
            {showSearchDropdown && (
              <div className="max-w-lg mx-auto -mt-4 relative z-50">
                <SearchDropdown
                  results={searchResults!}
                  onSelect={handleSelectEntity}
                />
              </div>
            )}
          </>
        ) : detailLoading ? (
          <div className="space-y-4">
            <div className="h-32 rounded-2xl shimmer" />
            <div className="h-24 rounded-2xl shimmer" />
            <div className="h-48 rounded-2xl shimmer" />
          </div>
        ) : !entity ? (
          <div className="text-center py-16">
            <p className="text-sm text-text-muted">Entity not found.</p>
            <button
              onClick={() => setSelectedEntityId(null)}
              className="mt-3 text-sm text-accent-500 hover:text-accent-700 font-medium"
            >
              Back to search
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Entity Header Card */}
            <div className="glass-card p-6">
              <div className="flex items-start gap-4">
                <div
                  className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-white text-lg font-bold shadow-lg"
                  style={{
                    background: NODE_GRADIENTS[entity.type] || NODE_GRADIENTS.meeting,
                  }}
                >
                  {entity.type === "person" ? (
                    getInitials(entity.label)
                  ) : (
                    (() => {
                      const Icon = TYPE_ICONS[entity.type] ?? Hash;
                      return <Icon size={24} />;
                    })()
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-xl font-bold text-text-primary">
                      {entity.label}
                    </h2>
                    <span
                      className={`badge text-[10px] ${
                        entity.type === "person"
                          ? "badge-info"
                          : entity.type === "organization"
                            ? "badge-neutral"
                            : "badge-success"
                      }`}
                    >
                      {entity.type}
                    </span>
                  </div>
                  {typeof entity.properties.email === "string" && (
                    <p className="text-sm text-text-muted mt-0.5">
                      {entity.properties.email}
                    </p>
                  )}
                  <div className="flex items-center gap-5 mt-3 text-xs text-text-muted">
                    <span className="flex items-center gap-1.5">
                      <Users size={13} />
                      {neighbors.length} connections
                    </span>
                    <span className="flex items-center gap-1.5">
                      <MessageSquare size={13} />
                      {meetings.length} meetings
                    </span>
                    {topicNeighbors.length > 0 && (
                      <span className="flex items-center gap-1.5">
                        <Hash size={13} />
                        {topicNeighbors.length} topics
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {entity.type === "person" && (
                    <Link
                      href={`/profiles/${entity.id}`}
                      className="btn-gradient flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold"
                    >
                      <User size={13} />
                      View Profile
                    </Link>
                  )}
                  <button
                    onClick={() => {
                      setSelectedEntityId(null);
                      setSearchQuery("");
                    }}
                    className="p-2 rounded-lg text-text-muted hover:text-text-secondary hover:bg-surface-overlay transition-colors"
                    title="Clear selection"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* View toggle */}
            <div className="flex items-center justify-between">
              <div className="flex rounded-xl bg-surface-overlay border border-border p-1 text-sm">
                <button
                  onClick={() => setViewMode("cards")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 font-semibold transition-all ${
                    viewMode === "cards"
                      ? "bg-white text-text-primary shadow-md"
                      : "text-text-muted hover:text-text-secondary"
                  }`}
                >
                  <LayoutList size={16} />
                  Cards
                </button>
                <button
                  onClick={() => setViewMode("graph")}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 font-semibold transition-all ${
                    viewMode === "graph"
                      ? "bg-white text-text-primary shadow-md"
                      : "text-text-muted hover:text-text-secondary"
                  }`}
                >
                  <Network size={16} />
                  Graph
                </button>
              </div>
              <p className="text-xs text-text-muted">
                {viewMode === "graph"
                  ? "Click a node to explore its connections"
                  : `Showing ${neighbors.length} connections`}
              </p>
            </div>

            {/* Graph view */}
            {viewMode === "graph" && graphNodes.length > 0 && (
              <MiniGraph
                nodes={graphNodes}
                edges={graphEdges}
                onNodeClick={handleSelectEntity}
              />
            )}

            {/* Connections */}
            {viewMode === "cards" && personNeighbors.length > 0 && (
              <section className="glass-card p-5">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3">
                  <Users size={15} className="text-accent-500" />
                  People ({personNeighbors.length})
                </h3>
                <div className="flex gap-1 overflow-x-auto pb-2 -mx-1 px-1">
                  {personNeighbors.slice(0, 20).map((n, i) => (
                    <ConnectionCard
                      key={n.id}
                      neighbor={n}
                      index={i}
                      onSelect={handleSelectEntity}
                    />
                  ))}
                  {personNeighbors.length > 20 && (
                    <div className="flex items-center justify-center min-w-[80px] text-xs text-text-muted">
                      +{personNeighbors.length - 20} more
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Orgs */}
            {viewMode === "cards" && orgNeighbors.length > 0 && (
              <section className="glass-card p-5">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3">
                  <Building2 size={15} className="text-violet-500" />
                  Organizations ({orgNeighbors.length})
                </h3>
                <div className="flex gap-1 overflow-x-auto pb-2 -mx-1 px-1">
                  {orgNeighbors.map((n, i) => (
                    <ConnectionCard
                      key={n.id}
                      neighbor={n}
                      index={i + 2}
                      onSelect={handleSelectEntity}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Topics */}
            {viewMode === "cards" && topicNeighbors.length > 0 && (
              <section className="glass-card p-5">
                <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3">
                  <Hash size={15} className="text-cyan-500" />
                  Topics ({topicNeighbors.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {topicNeighbors.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => handleSelectEntity(t.id)}
                      className="px-3 py-1.5 text-xs rounded-full bg-cyan-50 text-cyan-700 border border-cyan-200 hover:bg-cyan-100 transition-colors font-medium"
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </section>
            )}

            {/* Meetings */}
            <section className="glass-card p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3">
                <MessageSquare size={15} className="text-accent-500" />
                Meetings ({meetings.length})
              </h3>
              {meetingsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 rounded-xl shimmer" />
                  ))}
                </div>
              ) : meetings.length === 0 ? (
                <p className="text-sm text-text-muted py-4 text-center">
                  No meetings found for this entity.
                </p>
              ) : (
                <div className="space-y-1 max-h-[500px] overflow-y-auto">
                  {meetings.map((m) => (
                    <MeetingRow key={m.id} meeting={m} />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Search dropdown (shared between empty state & inline search)
// ---------------------------------------------------------------------------

function SearchDropdown({
  results,
  onSelect,
}: {
  results: Array<{ id: string; name: string; type: string }>;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="max-h-64 overflow-y-auto rounded-xl border border-border bg-surface-raised shadow-xl">
      {results.map((r) => {
        const Icon = TYPE_ICONS[r.type] ?? User;
        return (
          <button
            key={r.id}
            onClick={() => onSelect(r.id)}
            className="flex w-full items-center gap-2.5 px-4 py-3 text-left text-sm hover:bg-accent-50/50 transition-colors border-b border-border/50 last:border-b-0"
          >
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white text-[10px] font-bold"
              style={{
                background: NODE_GRADIENTS[r.type] || NODE_GRADIENTS.meeting,
              }}
            >
              {r.type === "person" ? getInitials(r.name) : <Icon size={14} />}
            </div>
            <span className="truncate text-text-primary font-medium">
              {r.name}
            </span>
            <span className="ml-auto badge badge-neutral text-[10px] shrink-0">
              {r.type}
            </span>
          </button>
        );
      })}
    </div>
  );
}
