"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { toast } from "sonner";
import {
  Key,
  Plug,
  ExternalLink,
  XCircle,
  CheckCircle,
  AlertCircle,
  Eye,
  EyeOff,
  Save,
  Trash2,
  Shield,
  Database,
  Loader2,
} from "lucide-react";

const STATUS_ICON: Record<string, { icon: typeof CheckCircle; color: string }> = {
  connected: { icon: CheckCircle, color: "text-emerald-500" },
  disconnected: { icon: XCircle, color: "text-text-muted" },
  error: { icon: AlertCircle, color: "text-red-500" },
};

type Tab = "general" | "connections";

interface SettingItem {
  key: string;
  label: string;
  value: string;
  is_secret: boolean;
  is_set: boolean;
  source: string;
  help_url?: string;
  placeholder?: string;
  readonly?: boolean;
}

function SettingField({ setting }: { setting: SettingItem }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [showValue, setShowValue] = useState(false);

  const updateMutation = useMutation({
    mutationFn: (value: string) => api.settings.update(setting.key, value),
    onSuccess: (data) => {
      toast.success(data.message);
      queryClient.invalidateQueries({ queryKey: ["app-settings"] });
      setEditing(false);
      setInputValue("");
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to save");
    },
  });

  const removeMutation = useMutation({
    mutationFn: () => api.settings.remove(setting.key),
    onSuccess: (data) => {
      toast.success(data.message);
      queryClient.invalidateQueries({ queryKey: ["app-settings"] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to remove");
    },
  });

  const isReadonly = !!setting.readonly;

  return (
    <div className="glass-card p-5 overflow-hidden">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="icon-box icon-box-md icon-box-indigo">
            <Key size={18} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-semibold text-text-primary">
                {setting.label}
              </h3>
              {setting.is_set ? (
                <span className="badge badge-success text-[10px]">
                  <CheckCircle size={9} className="mr-0.5" />
                  configured
                </span>
              ) : (
                <span className="badge badge-neutral text-[10px]">
                  not set
                </span>
              )}
              {setting.source === "env" && setting.is_set && (
                <span className="badge badge-info text-[10px] gap-0.5">
                  <Shield size={8} /> from .env
                </span>
              )}
              {setting.source === "database" && (
                <span className="badge badge-info text-[10px] gap-0.5">
                  <Database size={8} /> stored
                </span>
              )}
            </div>

            {!editing && setting.is_set && (
              <div className="mt-1.5 min-w-0">
                <code className="text-xs text-text-muted font-mono bg-surface-secondary/60 rounded px-2 py-0.5 inline-block max-w-full truncate align-middle">
                  {setting.value}
                </code>
              </div>
            )}

            {!setting.is_set && isReadonly && (
              <p className="mt-1 text-xs text-text-muted italic">
                {setting.placeholder || "Will be set automatically"}
              </p>
            )}

            {setting.help_url && (
              <a
                href={setting.help_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-[11px] text-accent-500 hover:text-accent-700 transition-colors"
              >
                View available models <ExternalLink size={10} />
              </a>
            )}

            {editing && (
              <div className="mt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <div className="relative flex-1 min-w-0">
                  <input
                    type={setting.is_secret && !showValue ? "password" : "text"}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder={setting.placeholder || `Enter ${setting.label.toLowerCase()}...`}
                    className={`w-full rounded-xl border border-border px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.1)] transition-all ${setting.is_secret ? "pr-9 font-mono" : ""}`}
                    autoFocus
                  />
                  {setting.is_secret && (
                    <button
                      type="button"
                      onClick={() => setShowValue(!showValue)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
                    >
                      {showValue ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  )}
                </div>
                <button
                  onClick={() => {
                    if (inputValue.trim()) updateMutation.mutate(inputValue.trim());
                  }}
                  disabled={!inputValue.trim() || updateMutation.isPending}
                  className="flex items-center gap-1 rounded-xl gradient-bg px-3 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
                >
                  {updateMutation.isPending ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Save size={12} />
                  )}
                  Save
                </button>
                <button
                  onClick={() => {
                    setEditing(false);
                    setInputValue("");
                  }}
                  className="rounded-xl border border-border px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-overlay transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>

        {!editing && !isReadonly && (
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                setEditing(true);
                setInputValue("");
                setShowValue(false);
              }}
              className="rounded-xl border border-border px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-overlay transition-colors"
            >
              {setting.is_set ? "Change" : "Set"}
            </button>
            {setting.source === "database" && (
              <button
                onClick={() => removeMutation.mutate()}
                disabled={removeMutation.isPending}
                className="flex items-center gap-1 rounded-xl border border-red-200 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
                title="Remove from database (falls back to .env)"
              >
                <Trash2 size={11} /> Remove
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const queryClient = useQueryClient();

  const { data: settingsData, isLoading: settingsLoading } = useQuery({
    queryKey: ["app-settings"],
    queryFn: () => api.settings.list(),
  });

  const { data: connections, isLoading: connectionsLoading } = useQuery({
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

  const tabs: { id: Tab; label: string; icon: typeof Key }[] = [
    { id: "general", label: "API Keys", icon: Key },
    { id: "connections", label: "Connections", icon: Plug },
  ];

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">
          Settings
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Manage API keys, connections, and app configuration
        </p>
      </div>

      <div className="tab-pills mb-6">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`tab-pill ${activeTab === tab.id ? "tab-pill-active" : ""}`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* API Keys tab */}
      {activeTab === "general" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Shield size={14} className="text-accent-400" />
            <p className="text-xs text-text-muted">
              API keys are encrypted at rest. Values stored here override .env
              file settings and take effect immediately.
            </p>
          </div>

          {settingsLoading && (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="h-20 rounded-2xl shimmer" />
              ))}
            </div>
          )}

          {settingsData?.items.map((setting) => (
            <SettingField key={setting.key} setting={setting} />
          ))}
        </div>
      )}

      {/* Connections tab */}
      {activeTab === "connections" && (
        <div className="space-y-4">
          {connectionsLoading && (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="h-24 rounded-2xl shimmer" />
              ))}
            </div>
          )}

          {connections?.map((conn) => {
            const statusConfig =
              STATUS_ICON[conn.status] || STATUS_ICON.disconnected;
            const StatusIcon = statusConfig.icon;

            return (
              <div key={conn.provider} className="glass-card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="icon-box icon-box-md icon-box-cyan">
                      <Plug size={18} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-text-primary capitalize">
                          {conn.provider}
                        </h3>
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
                          Last synced:{" "}
                          {new Date(conn.last_sync).toLocaleString()}
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
                    {conn.status === "disconnected" ||
                    conn.status === "error" ? (
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
                        onClick={() =>
                          disconnectMutation.mutate(conn.provider)
                        }
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
