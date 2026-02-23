"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { formatDistanceToNow } from "date-fns";
import {
  MessageSquare,
  CheckSquare,
  Bot,
  Plug,
  Clock,
  ArrowRight,
} from "lucide-react";

export default function DashboardPage() {
  const { data: meetings } = useQuery({
    queryKey: ["meetings", "dashboard"],
    queryFn: () => api.meetings.list(1, 5),
  });

  const { data: actionItems } = useQuery({
    queryKey: ["actionItems", "open"],
    queryFn: () => api.actionItems.list("open"),
  });

  const { data: connections } = useQuery({
    queryKey: ["connections"],
    queryFn: () => api.connections.list(),
  });

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.agents.list(),
  });

  const connectedCount = connections?.filter((c) => c.status === "connected").length ?? 0;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">
          Dashboard
        </h1>
        <p className="text-sm text-text-muted mt-1">
          Your meeting intelligence at a glance
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          icon={<MessageSquare size={20} />}
          label="Total Meetings"
          value={meetings?.total ?? "—"}
          href="/meetings"
          gradient="stat-gradient-1"
        />
        <StatCard
          icon={<CheckSquare size={20} />}
          label="Open Actions"
          value={actionItems?.total ?? "—"}
          href="/action-items"
          gradient="stat-gradient-2"
        />
        <StatCard
          icon={<Plug size={20} />}
          label="Connected"
          value={`${connectedCount}/${connections?.length ?? 0}`}
          href="/settings/connections"
          gradient="stat-gradient-3"
        />
        <StatCard
          icon={<Bot size={20} />}
          label="Agents"
          value={agents?.length ?? "—"}
          href="/agents"
          gradient="stat-gradient-4"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Meetings */}
        <section className="glass-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-text-primary tracking-wide uppercase">
              Recent Meetings
            </h2>
            <Link
              href="/meetings"
              className="flex items-center gap-1 text-xs text-accent-500 hover:text-accent-700 font-medium transition-colors"
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {meetings?.items.length ? (
            <ul className="space-y-2">
              {meetings.items.map((m) => (
                <li key={m.id}>
                  <Link
                    href={`/meetings/${m.id}`}
                    className="block rounded-xl p-3 hover:bg-accent-50/50 transition-colors border-l-2 border-transparent hover:border-accent-400"
                  >
                    <p className="text-sm font-medium text-text-primary truncate">
                      {m.title}
                    </p>
                    <p className="text-xs text-text-muted mt-1 flex items-center gap-1">
                      <Clock size={11} className="text-accent-400" />
                      {formatDistanceToNow(new Date(m.date), { addSuffix: true })}
                      {m.duration && ` · ${m.duration} min`}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">No meetings yet</p>
          )}
        </section>

        {/* Open Action Items */}
        <section className="glass-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-text-primary tracking-wide uppercase">
              Open Action Items
            </h2>
            <Link
              href="/action-items"
              className="flex items-center gap-1 text-xs text-accent-500 hover:text-accent-700 font-medium transition-colors"
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {actionItems?.items.length ? (
            <ul className="space-y-2">
              {actionItems.items.slice(0, 5).map((ai) => (
                <li key={ai.id} className="flex items-start gap-3 p-2 rounded-xl hover:bg-accent-50/50 transition-colors border-l-2 border-transparent hover:border-amber-400">
                  <div className="mt-0.5 h-4 w-4 shrink-0 rounded-md border-2 border-accent-300" />
                  <div className="min-w-0">
                    <p className="text-sm text-text-primary">{ai.description}</p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {ai.assignee}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">No open action items</p>
          )}
        </section>

        {/* Connections */}
        <section className="glass-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-text-primary tracking-wide uppercase">
              MCP Connections
            </h2>
            <Link
              href="/settings/connections"
              className="flex items-center gap-1 text-xs text-accent-500 hover:text-accent-700 font-medium transition-colors"
            >
              Manage <ArrowRight size={12} />
            </Link>
          </div>
          {connections?.length ? (
            <ul className="space-y-2">
              {connections.map((c) => (
                <li key={c.provider} className="flex items-center justify-between p-3 rounded-xl hover:bg-accent-50/50 transition-colors border-l-2 border-transparent hover:border-cyan-400">
                  <div>
                    <p className="text-sm font-medium text-text-primary capitalize">
                      {c.provider}
                    </p>
                    <p className="text-xs text-text-muted">{c.description}</p>
                  </div>
                  <span
                    className={`badge ${
                      c.status === "connected"
                        ? "badge-success"
                        : c.status === "error"
                          ? "badge-error"
                          : "badge-neutral"
                    }`}
                  >
                    {c.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">Loading connections...</p>
          )}
        </section>

        {/* Agents */}
        <section className="glass-card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-semibold text-text-primary tracking-wide uppercase">
              AI Agents
            </h2>
            <Link
              href="/agents"
              className="flex items-center gap-1 text-xs text-accent-500 hover:text-accent-700 font-medium transition-colors"
            >
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {agents?.length ? (
            <ul className="space-y-2">
              {agents.map((a) => (
                <li key={a.name} className="flex items-center justify-between p-3 rounded-xl hover:bg-accent-50/50 transition-colors border-l-2 border-transparent hover:border-violet-400">
                  <div>
                    <p className="text-sm font-medium text-text-primary">
                      {a.name.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-text-muted">{a.description}</p>
                  </div>
                  <span className="badge badge-info">
                    {a.pipeline}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">No agents registered</p>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  href,
  gradient,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  href: string;
  gradient: string;
}) {
  return (
    <Link
      href={href}
      className="group relative overflow-hidden rounded-2xl p-5 transition-all hover:shadow-lg hover:-translate-y-0.5"
    >
      <div className={`absolute inset-0 ${gradient} opacity-90`} />
      <div className="relative z-10">
        <div className="flex items-center gap-2 text-white/80 mb-3">{icon}</div>
        <p className="text-3xl font-bold text-white">{value}</p>
        <p className="text-xs text-white/70 mt-1 font-medium">{label}</p>
      </div>
      <div className="absolute -bottom-4 -right-4 h-20 w-20 rounded-full bg-white/10" />
      <div className="absolute -top-2 -right-2 h-12 w-12 rounded-full bg-white/5" />
    </Link>
  );
}
