"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeMouseHandler,
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
  ExternalLink,
  MessageSquare,
} from "lucide-react";
import Link from "next/link";

const NODE_COLORS: Record<string, string> = {
  person: "#6366f1",
  organization: "#8b5cf6",
  topic: "#06b6d4",
  project: "#f59e0b",
  meeting: "#64748b",
};

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

interface ForceNode extends SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

function computeForceLayout(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
  width: number,
  height: number,
): { flowNodes: Node[]; flowEdges: Edge[] } {
  if (!graphNodes.length)
    return { flowNodes: [], flowEdges: [] };

  const simNodes: ForceNode[] = graphNodes.map((n) => ({
    id: n.id,
    label: n.label,
    type: n.type,
    properties: n.properties,
    x: width / 2 + (Math.random() - 0.5) * 400,
    y: height / 2 + (Math.random() - 0.5) * 400,
  }));

  const nodeIds = new Set(simNodes.map((n) => n.id));

  const simLinks: SimulationLinkDatum<ForceNode>[] = graphEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({ source: e.source, target: e.target }));

  const sim = forceSimulation(simNodes)
    .force("charge", forceManyBody().strength(-300))
    .force(
      "link",
      forceLink<ForceNode, SimulationLinkDatum<ForceNode>>(simLinks)
        .id((d) => d.id)
        .distance(140),
    )
    .force("center", forceCenter(width / 2, height / 2))
    .force("collision", forceCollide(50))
    .stop();

  for (let i = 0; i < 200; i++) sim.tick();

  const meetingCount = (n: ForceNode) => {
    const mc = n.properties?.meeting_count;
    return typeof mc === "number" ? mc : 1;
  };

  const flowNodes: Node[] = simNodes.map((n) => {
    const mc = meetingCount(n);
    const size = Math.max(44, Math.min(84, 34 + mc * 3));
    return {
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
        fontSize: n.type === "person" ? "12px" : "10px",
        fontWeight: 600,
        width: size,
        textAlign: "center" as const,
        cursor: "pointer",
        boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
        letterSpacing: "0.01em",
      },
    };
  });

  const flowEdges: Edge[] = graphEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => {
      const strength = (e.properties?.strength as number) ?? 1;
      const isKnows = e.type === "KNOWS";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: isKnows ? "" : e.type,
        type: "default",
        animated: false,
        style: {
          stroke: isKnows ? "#a5b4fc" : "#cbd5e1",
          strokeWidth: Math.min(5, Math.max(1, strength)),
          strokeDasharray: isKnows ? undefined : "5 3",
        },
        labelStyle: { fontSize: "9px", fill: "#94a3b8" },
      };
    });

  return { flowNodes, flowEdges };
}

export default function RelationshipsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("person");
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: graphData, isLoading } = useQuery({
    queryKey: ["relationships", typeFilter],
    queryFn: () =>
      api.relationships.graph({ type: typeFilter || undefined, limit: 300 }),
  });

  const { data: expandData } = useQuery({
    queryKey: ["relationships", "expand", expandedNodeId],
    queryFn: () => api.relationships.entity(expandedNodeId!),
    enabled: !!expandedNodeId,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["relationships", "search", searchQuery],
    queryFn: () => api.relationships.search(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const { data: entityDetail } = useQuery({
    queryKey: ["relationships", "entity", selectedNodeId],
    queryFn: () => api.relationships.entity(selectedNodeId!),
    enabled: !!selectedNodeId,
  });

  const { data: entityMeetings } = useQuery({
    queryKey: ["relationships", "meetings", selectedNodeId],
    queryFn: () => api.relationships.meetings(selectedNodeId!),
    enabled: !!selectedNodeId,
  });

  const mergedGraph = useMemo(() => {
    if (!graphData) return { nodes: [], edges: [] };

    const nodes = [...graphData.nodes];
    const edges = [...graphData.edges];

    if (expandData && expandedNodeId) {
      const existingIds = new Set(nodes.map((n) => n.id));
      for (const neighbor of expandData.neighbors) {
        if (!existingIds.has(neighbor.id)) {
          nodes.push(neighbor as GraphNode);
          existingIds.add(neighbor.id);
        }
      }
      const existingEdgeIds = new Set(edges.map((e) => e.id));
      for (const edge of expandData.edges) {
        if (
          !existingEdgeIds.has(edge.id) &&
          existingIds.has(edge.source) &&
          existingIds.has(edge.target)
        ) {
          edges.push(edge as GraphEdge);
        }
      }
    }

    return { nodes, edges };
  }, [graphData, expandData, expandedNodeId]);

  const elements = useMemo(() => {
    if (!mergedGraph.nodes.length)
      return { flowNodes: [], flowEdges: [] };
    const w = containerRef.current?.clientWidth ?? 900;
    const h = containerRef.current?.clientHeight ?? 600;
    return computeForceLayout(mergedGraph.nodes, mergedGraph.edges, w, h);
  }, [mergedGraph]);

  const [nodes, setNodes, onNodesChange] = useNodesState(elements.flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(elements.flowEdges);

  useEffect(() => {
    setNodes(elements.flowNodes);
    setEdges(elements.flowEdges);
  }, [elements, setNodes, setEdges]);

  useEffect(() => {
    if (!searchQuery || !searchResults?.length) {
      setNodes((prev) =>
        prev.map((n) => ({
          ...n,
          style: { ...n.style, opacity: 1, boxShadow: "0 4px 12px rgba(0,0,0,0.1)" },
        })),
      );
      return;
    }
    const matchIds = new Set(searchResults.map((r) => r.id));
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        style: {
          ...n.style,
          opacity: matchIds.has(n.id) ? 1 : 0.15,
          boxShadow: matchIds.has(n.id)
            ? "0 0 0 3px rgba(99,102,241,0.5), 0 4px 16px rgba(99,102,241,0.3)"
            : "0 4px 12px rgba(0,0,0,0.05)",
        },
      })),
    );
  }, [searchResults, searchQuery, setNodes]);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      setSelectedNodeId(node.id);
      if (expandedNodeId === node.id) {
        setExpandedNodeId(null);
      } else {
        setExpandedNodeId(node.id);
      }
    },
    [expandedNodeId],
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
    setExpandedNodeId(null);
  }, []);

  const handleSearchResultClick = (id: string) => {
    setSearchQuery("");
    setSelectedNodeId(id);
    setExpandedNodeId(id);
  };

  const detail = entityDetail?.entity;
  const detailNeighbors = entityDetail?.neighbors ?? [];
  const meetingIds = entityMeetings?.meeting_ids ?? [];

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col" ref={containerRef}>
        {/* Header */}
        <div className="border-b border-border bg-surface-raised px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold tracking-tight text-text-primary">
                Relationships
              </h1>
              <p className="text-xs text-text-muted mt-0.5">
                Click a node to expand connections
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex rounded-xl bg-surface-overlay p-0.5 text-xs">
                {[
                  { value: "person", label: "People" },
                  { value: "organization", label: "Orgs" },
                  { value: "topic", label: "Topics" },
                  { value: "", label: "All" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setTypeFilter(opt.value);
                      setExpandedNodeId(null);
                      setSelectedNodeId(null);
                    }}
                    className={`rounded-lg px-3 py-1.5 font-medium transition-all ${
                      typeFilter === opt.value
                        ? "bg-white text-text-primary shadow-sm"
                        : "text-text-muted hover:text-text-secondary"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="relative mt-3 max-w-sm">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search people, orgs, topics..."
              className="w-full rounded-xl border border-border bg-surface py-2 pl-9 pr-8 text-xs text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.1)] placeholder:text-text-muted transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              >
                <X size={14} />
              </button>
            )}
            {searchQuery.length >= 2 && searchResults && searchResults.length > 0 && (
              <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-48 overflow-y-auto rounded-xl border border-border bg-surface-raised shadow-xl">
                {searchResults.map((r) => {
                  const Icon = TYPE_ICONS[r.type] ?? User;
                  return (
                    <button
                      key={r.id}
                      onClick={() => handleSearchResultClick(r.id)}
                      className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-xs hover:bg-accent-50/50 transition-colors"
                    >
                      <Icon size={12} className="text-text-muted shrink-0" />
                      <span className="truncate text-text-primary font-medium">{r.name}</span>
                      <span className="ml-auto badge badge-neutral text-[10px]">
                        {r.type}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="mt-2 flex items-center gap-4">
            {Object.entries(NODE_COLORS)
              .filter(([type]) =>
                typeFilter ? type === typeFilter || type !== typeFilter : true,
              )
              .slice(0, 5)
              .map(([type, color]) => (
                <span
                  key={type}
                  className="flex items-center gap-1.5 text-[10px] text-text-muted font-medium"
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: color }}
                  />
                  {type}
                </span>
              ))}
            <span className="text-[10px] text-text-muted">
              {mergedGraph.nodes.length} nodes, {mergedGraph.edges.length} edges
            </span>
          </div>
        </div>

        {/* Graph */}
        <div className="flex-1 bg-surface">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent-200 border-t-accent-600" />
            </div>
          ) : nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <p className="text-sm text-text-muted">No entities found.</p>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              fitView
              proOptions={{ hideAttribution: true }}
              minZoom={0.2}
              maxZoom={2}
            >
              <Background color="#e2e8f0" gap={24} />
              <Controls
                style={{ bottom: 16, left: 16 }}
                showInteractive={false}
              />
              <MiniMap
                nodeColor={(n) =>
                  (n.style?.background as string) || "#6b7280"
                }
                style={{ bottom: 16, right: 16 }}
                maskColor="rgba(0,0,0,0.05)"
              />
            </ReactFlow>
          )}
        </div>
      </div>

      {/* Detail Panel */}
      {selectedNodeId && detail && (
        <div className="w-80 shrink-0 border-l border-border bg-surface-raised overflow-y-auto">
          <div className="p-5">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-2">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-white text-xs font-bold"
                  style={{
                    background: NODE_GRADIENTS[detail.type] || NODE_GRADIENTS.meeting,
                  }}
                >
                  {detail.label
                    .split(" ")
                    .map((w) => w[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-bold text-text-primary">
                    {detail.label}
                  </p>
                  <p className="text-[10px] text-text-muted capitalize font-medium">
                    {detail.type}
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setSelectedNodeId(null);
                  setExpandedNodeId(null);
                }}
                className="text-text-muted hover:text-text-secondary transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {detail.properties.email ? (
              <p className="text-xs text-text-muted mb-3">
                {String(detail.properties.email)}
              </p>
            ) : null}

            <div className="mb-4">
              <h3 className="text-xs font-semibold text-text-muted mb-2 uppercase tracking-wide">
                Connections ({detailNeighbors.length})
              </h3>
              {detailNeighbors.length === 0 ? (
                <p className="text-xs text-text-muted">No connections found</p>
              ) : (
                <ul className="space-y-1 max-h-48 overflow-y-auto">
                  {detailNeighbors.slice(0, 20).map((n) => {
                    const Icon = TYPE_ICONS[n.type] ?? User;
                    return (
                      <li key={n.id}>
                        <button
                          onClick={() => {
                            setSelectedNodeId(n.id);
                            setExpandedNodeId(n.id);
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs text-text-primary hover:bg-accent-50/50 transition-colors"
                        >
                          <Icon size={12} className="text-text-muted shrink-0" />
                          <span className="truncate font-medium">{n.label}</span>
                          <span
                            className="ml-auto h-2.5 w-2.5 rounded-full shrink-0"
                            style={{
                              background: NODE_COLORS[n.type] || "#6b7280",
                            }}
                          />
                        </button>
                      </li>
                    );
                  })}
                  {detailNeighbors.length > 20 && (
                    <p className="text-[10px] text-text-muted px-2">
                      +{detailNeighbors.length - 20} more
                    </p>
                  )}
                </ul>
              )}
            </div>

            <div className="mb-4">
              <h3 className="text-xs font-semibold text-text-muted mb-2 uppercase tracking-wide">
                <MessageSquare size={11} className="inline mr-1" />
                Meetings ({meetingIds.length})
              </h3>
              {meetingIds.length === 0 ? (
                <p className="text-xs text-text-muted">No meetings linked</p>
              ) : (
                <ul className="space-y-1 max-h-40 overflow-y-auto">
                  {meetingIds.slice(0, 10).map((mid) => (
                    <li key={mid}>
                      <Link
                        href={`/meetings/${mid}`}
                        className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-xs text-accent-600 hover:bg-accent-50/50 hover:text-accent-700 transition-colors"
                      >
                        <ExternalLink size={10} className="shrink-0" />
                        <span className="truncate">{mid.slice(0, 8)}...</span>
                      </Link>
                    </li>
                  ))}
                  {meetingIds.length > 10 && (
                    <p className="text-[10px] text-text-muted px-2">
                      +{meetingIds.length - 10} more meetings
                    </p>
                  )}
                </ul>
              )}
            </div>

            {detail.type === "person" && (
              <Link
                href={`/profiles/${detail.id}`}
                className="block rounded-xl gradient-bg px-4 py-2.5 text-center text-xs font-semibold text-white hover:opacity-90 transition-all shadow-lg shadow-accent-500/25"
              >
                View Full Profile
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
