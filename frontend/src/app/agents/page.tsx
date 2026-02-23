"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Bot, Clock, CheckCircle, AlertCircle, Play, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function AgentsPage() {
  const queryClient = useQueryClient();

  const { data: agents, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.agents.list(),
    refetchInterval: 5000,
  });

  const triggerMutation = useMutation({
    mutationFn: (name: string) => api.agents.trigger(name),
    onSuccess: (data) => {
      toast.success(`Agent "${data.agent_name.replace(/_/g, " ")}" triggered`);
      queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (err: Error) => {
      toast.error(err.message || "Failed to trigger agent");
    },
  });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">AI Agents</h1>
        <p className="text-sm text-text-muted mt-1">
          Monitor agent status, execution history, and trigger runs
        </p>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 rounded-2xl shimmer" />
          ))}
        </div>
      )}

      {agents && (
        <div className="space-y-4">
          {agents.map((agent) => (
            <div key={agent.name} className="glass-card p-6">
              <div className="flex items-start justify-between gap-4">
                <Link
                  href={`/agents/${agent.name}`}
                  className="min-w-0 flex-1 group"
                >
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl gradient-bg">
                      <Bot size={16} className="text-white" />
                    </div>
                    <h2 className="text-base font-semibold text-text-primary group-hover:text-accent-600 transition-colors">
                      {agent.name.replace(/_/g, " ")}
                    </h2>
                    <span className="badge badge-info">{agent.pipeline}</span>
                  </div>
                  <p className="mt-2 text-sm text-text-secondary">
                    {agent.description}
                  </p>

                  <div className="mt-3 flex items-center gap-4 text-xs text-text-muted">
                    {agent.dependencies.length > 0 && (
                      <span>
                        Depends on:{" "}
                        {agent.dependencies
                          .map((d) => d.replace(/_/g, " "))
                          .join(", ")}
                      </span>
                    )}
                    {agent.required_mcp_providers.length > 0 && (
                      <span>
                        Requires: {agent.required_mcp_providers.join(", ")}
                      </span>
                    )}
                  </div>
                </Link>

                <div className="flex flex-col items-end gap-2 shrink-0">
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <div className="text-lg font-bold text-text-primary">
                        {agent.total_runs}
                        <span className="text-xs font-normal text-text-muted ml-1">
                          runs
                        </span>
                      </div>
                      {agent.success_rate !== null && (
                        <div className="flex items-center gap-1 text-xs justify-end">
                          {agent.success_rate >= 0.9 ? (
                            <CheckCircle size={12} className="text-emerald-500" />
                          ) : (
                            <AlertCircle size={12} className="text-amber-500" />
                          )}
                          <span className="text-text-secondary">
                            {Math.round(agent.success_rate * 100)}% success
                          </span>
                        </div>
                      )}
                    </div>

                    {agent.can_trigger && (
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          triggerMutation.mutate(agent.name);
                        }}
                        disabled={triggerMutation.isPending}
                        className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-500 hover:bg-accent-600 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                        title={`Run ${agent.name.replace(/_/g, " ")}`}
                      >
                        {triggerMutation.isPending ? (
                          <Loader2 size={16} className="animate-spin" />
                        ) : (
                          <Play size={16} />
                        )}
                      </button>
                    )}
                  </div>

                  {agent.last_run && (
                    <div className="flex items-center gap-1 text-xs text-text-muted">
                      <Clock size={11} />
                      {agent.last_run.duration_ms
                        ? `${(agent.last_run.duration_ms / 1000).toFixed(1)}s`
                        : "—"}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {agents.length === 0 && (
            <div className="rounded-2xl border-2 border-dashed border-border p-12 text-center">
              <Bot className="mx-auto h-10 w-10 text-text-muted" />
              <p className="mt-3 text-sm text-text-muted">
                No agents registered yet.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
