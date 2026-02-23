"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import {
  ArrowLeft,
  Bot,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Play,
  Loader2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";

const STATUS_STYLES: Record<
  string,
  { icon: typeof CheckCircle; color: string }
> = {
  completed: { icon: CheckCircle, color: "text-emerald-500" },
  failed: { icon: XCircle, color: "text-red-500" },
  running: { icon: Loader2, color: "text-blue-500" },
  partial: { icon: AlertCircle, color: "text-amber-500" },
};

export default function AgentDetailPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name } = use(params);
  const queryClient = useQueryClient();
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const { data: agent, isLoading } = useQuery({
    queryKey: ["agent", name],
    queryFn: () => api.agents.get(name),
    refetchInterval: 5000,
  });

  const { data: runsData } = useQuery({
    queryKey: ["agentRuns", name],
    queryFn: () => api.agents.runs(name),
    refetchInterval: 5000,
  });

  const triggerMutation = useMutation({
    mutationFn: () => api.agents.trigger(name),
    onSuccess: () => {
      toast.success(`Agent "${name.replace(/_/g, " ")}" triggered`);
      queryClient.invalidateQueries({ queryKey: ["agent", name] });
      queryClient.invalidateQueries({ queryKey: ["agentRuns", name] });
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to trigger agent");
    },
  });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link
        href="/agents"
        className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
      >
        <ArrowLeft size={14} /> Back to Agents
      </Link>

      {isLoading && (
        <div className="space-y-4">
          <div className="h-32 rounded-2xl shimmer" />
          <div className="h-64 rounded-2xl shimmer" />
        </div>
      )}

      {agent && (
        <>
          <div className="mb-8">
            <div className="flex items-center justify-between gap-4 mb-2">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl gradient-bg">
                  <Bot size={20} className="text-white" />
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-text-primary">
                  {name.replace(/_/g, " ")}
                </h1>
                <span className="badge badge-info">{agent.pipeline}</span>
              </div>

              {agent.can_trigger && (
                <button
                  onClick={() => triggerMutation.mutate()}
                  disabled={triggerMutation.isPending}
                  className="inline-flex items-center gap-2 rounded-xl bg-accent-500 hover:bg-accent-600 px-4 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                  {triggerMutation.isPending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Play size={16} />
                  )}
                  Run Agent
                </button>
              )}
            </div>
            <p className="text-sm text-text-secondary ml-[52px]">
              {agent.description}
            </p>

            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <div className="glass-card p-5">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                  Total Runs
                </p>
                <p className="text-2xl font-bold text-text-primary mt-1">
                  {agent.total_runs}
                </p>
              </div>
              <div className="glass-card p-5">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                  Success Rate
                </p>
                <p className="text-2xl font-bold text-text-primary mt-1">
                  {agent.success_rate !== null
                    ? `${Math.round(agent.success_rate * 100)}%`
                    : "—"}
                </p>
              </div>
              <div className="glass-card p-5">
                <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                  Dependencies
                </p>
                <p className="text-sm font-medium text-text-primary mt-1">
                  {agent.dependencies.length > 0
                    ? agent.dependencies
                        .map((d) => d.replace(/_/g, " "))
                        .join(", ")
                    : "None"}
                </p>
              </div>
            </div>
          </div>

          <section className="glass-card overflow-hidden">
            <div className="border-b border-border px-6 py-4">
              <h2 className="text-sm font-semibold text-text-primary uppercase tracking-wide">
                Run History
              </h2>
            </div>

            {runsData?.items.length ? (
              <div className="divide-y divide-border/50">
                {runsData.items.map((run) => {
                  const statusConfig =
                    STATUS_STYLES[run.status] || STATUS_STYLES.partial;
                  const StatusIcon = statusConfig.icon;
                  const isExpanded = expandedRun === run.id;

                  return (
                    <div key={run.id}>
                      <button
                        onClick={() =>
                          setExpandedRun(isExpanded ? null : run.id)
                        }
                        className="w-full flex items-center gap-4 px-6 py-4 hover:bg-accent-50/30 transition-colors text-left"
                      >
                        <StatusIcon
                          size={16}
                          className={`${statusConfig.color} ${run.status === "running" ? "animate-spin" : ""}`}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-text-primary">
                              {run.trigger || "manual"}
                            </span>
                            <span className="text-xs text-text-muted">
                              {format(
                                new Date(run.started_at),
                                "MMM d, h:mm a"
                              )}
                            </span>
                          </div>
                          <div className="mt-0.5 flex items-center gap-3 text-xs text-text-muted">
                            {run.duration_ms !== null && (
                              <span className="flex items-center gap-0.5">
                                <Clock size={10} />
                                {(run.duration_ms / 1000).toFixed(1)}s
                              </span>
                            )}
                            {run.meetings_processed > 0 && (
                              <span>{run.meetings_processed} meetings</span>
                            )}
                            {run.entities_extracted > 0 && (
                              <span>{run.entities_extracted} entities</span>
                            )}
                            {run.tokens_used > 0 && (
                              <span>
                                {run.tokens_used.toLocaleString()} tokens
                              </span>
                            )}
                            {run.errors_count > 0 && (
                              <span className="text-red-400">
                                {run.errors_count} errors
                              </span>
                            )}
                          </div>
                        </div>
                        {isExpanded ? (
                          <ChevronDown
                            size={14}
                            className="text-text-muted shrink-0"
                          />
                        ) : (
                          <ChevronRight
                            size={14}
                            className="text-text-muted shrink-0"
                          />
                        )}
                      </button>

                      {isExpanded && run.result_summary && (
                        <div className="px-6 pb-4 -mt-1">
                          <div className="ml-8 rounded-xl bg-surface-secondary/60 px-4 py-3">
                            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-1">
                              Result
                            </p>
                            <p className="text-sm text-text-secondary">
                              {run.result_summary}
                            </p>
                            {run.completed_at && (
                              <p className="text-xs text-text-muted mt-2">
                                Completed{" "}
                                {format(
                                  new Date(run.completed_at),
                                  "MMM d, h:mm:ss a"
                                )}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="px-6 py-12 text-center text-sm text-text-muted">
                No runs recorded yet. Click "Run Agent" to start one.
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
