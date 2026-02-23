"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Clock,
  Database,
  Cloud,
  RefreshCw,
  ChevronUp,
  Square,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function timeUntil(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff < 0) return "now";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

const STATUS_DOT: Record<string, string> = {
  healthy: "bg-emerald-400",
  degraded: "bg-amber-400",
  disconnected: "bg-zinc-400",
  completed: "bg-emerald-400",
  running: "bg-blue-400 animate-pulse",
  failed: "bg-red-400",
};

export function StatusBar() {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  const { data: status, isError } = useQuery({
    queryKey: ["system-status"],
    queryFn: () => api.status(),
    refetchInterval: 5000,
    retry: 1,
  });

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => api.cancelRun(runId),
    onSuccess: () => {
      toast.success("Run cancelled");
      queryClient.invalidateQueries({ queryKey: ["system-status"] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to cancel run");
    },
  });

  if (isError || !status) {
    return (
      <div className="border-t border-border bg-surface-raised px-4 py-1.5 flex items-center gap-2 text-xs text-text-muted">
        <XCircle size={12} className="text-red-400" />
        <span>Backend unavailable</span>
      </div>
    );
  }

  const hasActive = status.active_runs.length > 0;
  const hasStaleRun = status.active_runs.some((r) => r.elapsed_minutes > 5);
  const lastRun = status.recent_runs[0];

  return (
    <div className="border-t border-border bg-surface-raised">
      {/* Collapsed bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-1.5 text-xs hover:bg-surface-overlay transition-colors"
      >
        {/* Activity indicator */}
        <div className="flex items-center gap-1.5">
          {hasActive ? (
            hasStaleRun ? (
              <AlertTriangle size={12} className="text-amber-500" />
            ) : (
              <Loader2 size={12} className="animate-spin text-accent-500" />
            )
          ) : (
            <Activity size={12} className="text-emerald-500" />
          )}
          <span className={cn("font-medium", hasStaleRun ? "text-amber-600" : "text-text-secondary")}>
            {hasActive
              ? hasStaleRun
                ? `Stale run: ${status.active_runs.map((r) => r.pipeline).join(", ")}`
                : `Running: ${status.active_runs.map((r) => r.pipeline).join(", ")}`
              : "Idle"}
          </span>
        </div>

        <span className="text-border">|</span>

        {/* Provider status pills */}
        <div className="flex items-center gap-2">
          {status.providers.map((p) => (
            <div key={p.name} className="flex items-center gap-1">
              <div
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  STATUS_DOT[p.status] || STATUS_DOT.disconnected
                )}
              />
              <span className="text-text-muted capitalize">{p.name}</span>
              {p.source && (
                <span className="text-[10px] text-text-muted">
                  {p.source === "mcp" ? (
                    <Cloud size={9} className="inline -mt-px text-accent-400" />
                  ) : (
                    <Database size={9} className="inline -mt-px" />
                  )}
                </span>
              )}
            </div>
          ))}
        </div>

        <span className="text-border">|</span>

        {/* Last run */}
        {lastRun && (
          <div className="flex items-center gap-1 text-text-muted">
            <div
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                STATUS_DOT[lastRun.status] || STATUS_DOT.disconnected
              )}
            />
            <span>
              {lastRun.pipeline} {timeAgo(lastRun.started_at)}
            </span>
          </div>
        )}

        {/* Next sync */}
        {status.scheduler.next_sync && (
          <>
            <span className="text-border">|</span>
            <div className="flex items-center gap-1 text-text-muted">
              <Clock size={10} />
              <span>next sync in {timeUntil(status.scheduler.next_sync)}</span>
            </div>
          </>
        )}

        <div className="ml-auto">
          <ChevronUp
            size={12}
            className={cn(
              "text-text-muted transition-transform",
              !expanded && "rotate-180"
            )}
          />
        </div>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="border-t border-border px-4 py-3 space-y-3 bg-surface">
          {/* Providers */}
          <div>
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">
              Data Sources
            </h4>
            <div className="flex gap-3">
              {status.providers.map((p) => (
                <div
                  key={p.name}
                  className="flex items-center gap-2 rounded-lg border border-border bg-surface-raised px-3 py-1.5"
                >
                  <div
                    className={cn(
                      "h-2 w-2 rounded-full",
                      STATUS_DOT[p.status] || STATUS_DOT.disconnected
                    )}
                  />
                  <span className="text-xs font-medium text-text-primary capitalize">
                    {p.name}
                  </span>
                  <span
                    className={cn(
                      "badge text-[10px]",
                      p.status === "healthy"
                        ? "badge-success"
                        : p.status === "degraded"
                          ? "bg-amber-50 text-amber-600"
                          : "badge-neutral"
                    )}
                  >
                    {p.status}
                  </span>
                  {p.source && (
                    <span className="badge badge-info text-[10px] gap-1">
                      {p.source === "mcp" ? (
                        <>
                          <Cloud size={8} /> MCP API
                        </>
                      ) : (
                        <>
                          <Database size={8} /> Local Cache
                        </>
                      )}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Active runs */}
          {status.active_runs.length > 0 && (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">
                Active Pipelines
              </h4>
              <div className="space-y-1">
                {status.active_runs.map((run) => {
                  const elapsed = run.elapsed_minutes ?? 0;
                  const isStale = elapsed > 5;
                  return (
                    <div
                      key={run.id}
                      className={cn(
                        "flex items-center gap-2 rounded-lg border px-3 py-1.5",
                        isStale
                          ? "border-amber-300 bg-amber-50"
                          : "border-accent-200 bg-accent-50",
                      )}
                    >
                      {isStale ? (
                        <AlertTriangle size={12} className="text-amber-500 shrink-0" />
                      ) : (
                        <Loader2 size={12} className="animate-spin text-accent-500 shrink-0" />
                      )}
                      <span className={cn("text-xs font-medium", isStale ? "text-amber-700" : "text-accent-700")}>
                        {run.agent_name}
                      </span>
                      <span className={cn("text-[10px]", isStale ? "text-amber-600" : "text-accent-500")}>
                        {isStale
                          ? `stuck for ${Math.round(elapsed)}m — may need cancelling`
                          : `started ${timeAgo(run.started_at)}`}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          cancelMutation.mutate(run.id);
                        }}
                        disabled={cancelMutation.isPending}
                        className={cn(
                          "ml-auto flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium transition-colors",
                          isStale
                            ? "bg-amber-200 text-amber-800 hover:bg-amber-300"
                            : "bg-accent-100 text-accent-700 hover:bg-accent-200",
                        )}
                        title="Cancel this run"
                      >
                        <Square size={8} /> Cancel
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recent runs */}
          <div>
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-muted mb-1.5">
              Recent Activity
            </h4>
            <div className="space-y-1">
              {status.recent_runs.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center gap-2 text-xs px-1"
                >
                  {run.status === "completed" ? (
                    <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />
                  ) : run.status === "failed" ? (
                    <AlertTriangle size={12} className="text-red-500 shrink-0" />
                  ) : (
                    <Loader2
                      size={12}
                      className="animate-spin text-accent-500 shrink-0"
                    />
                  )}
                  <span className="font-medium text-text-primary">
                    {run.pipeline}
                  </span>
                  {run.meetings_processed > 0 && (
                    <span className="text-text-muted">
                      {run.meetings_processed} meetings
                    </span>
                  )}
                  {run.errors_count > 0 && (
                    <span className="text-red-500">
                      {run.errors_count} errors
                    </span>
                  )}
                  {run.duration_ms != null && (
                    <span className="text-text-muted">
                      {run.duration_ms > 1000
                        ? `${(run.duration_ms / 1000).toFixed(1)}s`
                        : `${run.duration_ms}ms`}
                    </span>
                  )}
                  <span className="ml-auto text-text-muted">
                    {timeAgo(run.started_at)}
                  </span>
                </div>
              ))}
              {status.recent_runs.length === 0 && (
                <p className="text-xs text-text-muted px-1">
                  No recent activity
                </p>
              )}
            </div>
          </div>

          {/* Scheduler */}
          <div className="flex gap-4 text-[11px] text-text-muted">
            {status.scheduler.next_sync && (
              <div className="flex items-center gap-1">
                <RefreshCw size={10} />
                Next sync: {timeUntil(status.scheduler.next_sync)}
              </div>
            )}
            {status.scheduler.next_briefing && (
              <div className="flex items-center gap-1">
                <Clock size={10} />
                Next briefing: {timeUntil(status.scheduler.next_briefing)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
