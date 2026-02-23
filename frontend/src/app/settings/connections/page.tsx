"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Plug, ExternalLink, XCircle, CheckCircle, AlertCircle } from "lucide-react";

const STATUS_ICON: Record<string, { icon: typeof CheckCircle; color: string }> = {
  connected: { icon: CheckCircle, color: "text-emerald-500" },
  disconnected: { icon: XCircle, color: "text-text-muted" },
  error: { icon: AlertCircle, color: "text-red-500" },
};

export default function ConnectionsPage() {
  const queryClient = useQueryClient();

  const { data: connections, isLoading } = useQuery({
    queryKey: ["connections"],
    queryFn: () => api.connections.list(),
  });

  const connectMutation = useMutation({
    mutationFn: async (provider: string) => {
      const { auth_url } = await api.connections.authUrl(provider);
      if (auth_url) {
        window.open(auth_url, "_blank", "noopener,noreferrer");
      }
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: (provider: string) => api.connections.disconnect(provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connections"] }),
  });

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">
          MCP Connections
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Manage your external tool connections
        </p>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-24 rounded-2xl shimmer" />
          ))}
        </div>
      )}

      {connections && (
        <div className="space-y-4">
          {connections.map((conn) => {
            const statusConfig = STATUS_ICON[conn.status] || STATUS_ICON.disconnected;
            const StatusIcon = statusConfig.icon;

            return (
              <div
                key={conn.provider}
                className="glass-card p-6"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-50">
                      <Plug size={18} className="text-accent-500" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold text-text-primary capitalize">
                          {conn.provider}
                        </h2>
                        <span
                          className={`badge ${
                            conn.status === "connected"
                              ? "badge-success"
                              : conn.status === "error"
                                ? "badge-error"
                                : "badge-neutral"
                          }`}
                        >
                          <StatusIcon size={10} className="mr-1" />
                          {conn.status}
                        </span>
                      </div>
                      <p className="mt-0.5 text-sm text-text-secondary">
                        {conn.description}
                      </p>
                      {conn.last_sync && (
                        <p className="mt-1 text-xs text-text-muted">
                          Last synced: {new Date(conn.last_sync).toLocaleString()}
                        </p>
                      )}
                      {conn.last_error && (
                        <p className="mt-1 text-xs text-red-500">
                          {conn.last_error}
                        </p>
                      )}
                    </div>
                  </div>

                  <div>
                    {conn.status === "disconnected" || conn.status === "error" ? (
                      <button
                        onClick={() => connectMutation.mutate(conn.provider)}
                        disabled={connectMutation.isPending}
                        className="flex items-center gap-1.5 rounded-xl gradient-bg px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
                      >
                        <ExternalLink size={13} />
                        Connect
                      </button>
                    ) : (
                      <button
                        onClick={() => disconnectMutation.mutate(conn.provider)}
                        disabled={disconnectMutation.isPending}
                        className="rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
                      >
                        Disconnect
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
