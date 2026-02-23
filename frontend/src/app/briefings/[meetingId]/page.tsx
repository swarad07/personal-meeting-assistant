"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Clock,
  ListChecks,
  Users,
  MessageSquare,
} from "lucide-react";
import { api } from "@/lib/api-client";
import type { Briefing } from "@/lib/types";

export default function BriefingPage({
  params,
}: {
  params: Promise<{ meetingId: string }>;
}) {
  const { meetingId } = use(params);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadBriefing();
  }, [meetingId]);

  async function loadBriefing() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.briefings.get(meetingId);
      setBriefing(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load briefing"
      );
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="space-y-4">
          <div className="h-8 w-64 rounded-xl shimmer" />
          <div className="h-4 w-48 rounded-xl shimmer" />
          <div className="h-64 rounded-2xl shimmer" />
        </div>
      </div>
    );
  }

  if (error || !briefing) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Link
          href="/calendar"
          className="inline-flex items-center gap-1 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
        >
          <ArrowLeft size={14} />
          Back to Calendar
        </Link>
        <div className="text-center py-16">
          <FileText size={48} className="mx-auto mb-4 text-text-muted" />
          <p className="text-lg font-semibold text-text-primary">
            Briefing not found
          </p>
          <p className="text-sm text-text-muted mt-1">
            {error || "This briefing does not exist or has been removed."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link
        href="/calendar"
        className="inline-flex items-center gap-1 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
      >
        <ArrowLeft size={14} />
        Back to Calendar
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          {briefing.title}
        </h1>
        <div className="flex items-center gap-4 mt-2 text-sm text-text-muted">
          {briefing.created_at && (
            <span className="flex items-center gap-1">
              <Clock size={14} />
              Generated{" "}
              {new Date(briefing.created_at).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
          {briefing.calendar_event_id && (
            <span className="text-text-muted/60">
              Event: {briefing.calendar_event_id}
            </span>
          )}
        </div>
      </div>

      <div className="space-y-6">
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText size={18} className="text-accent-500" />
            <h2 className="text-lg font-semibold text-text-primary">Briefing</h2>
          </div>
          <div className="prose prose-sm max-w-none text-text-secondary">
            {briefing.content.split("\n").map((line, i) => {
              if (line.startsWith("## ")) {
                return (
                  <h3 key={i} className="text-base font-semibold text-text-primary mt-4 mb-2">
                    {line.replace("## ", "")}
                  </h3>
                );
              }
              if (line.startsWith("- ")) {
                return (
                  <li key={i} className="ml-4">
                    {line.replace("- ", "")}
                  </li>
                );
              }
              if (line.trim() === "") return <br key={i} />;
              return <p key={i}>{line}</p>;
            })}
          </div>
        </section>

        {briefing.topics != null && Array.isArray(briefing.topics) && briefing.topics.length > 0 ? (
          <section className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare size={18} className="text-accent-500" />
              <h2 className="text-lg font-semibold text-text-primary">
                Discussion Points
              </h2>
            </div>
            <ul className="space-y-2">
              {briefing.topics.map((topic, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 text-sm text-text-secondary"
                >
                  <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-100 text-xs font-bold text-accent-700">
                    {i + 1}
                  </span>
                  {typeof topic === "string" ? topic : JSON.stringify(topic)}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {briefing.attendee_context != null ? (
          <section className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <Users size={18} className="text-accent-500" />
              <h2 className="text-lg font-semibold text-text-primary">
                Attendee Context
              </h2>
            </div>
            <div className="text-sm text-text-secondary">
              {Array.isArray(briefing.attendee_context) ? (
                <ul className="space-y-2">
                  {(briefing.attendee_context as string[]).map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-accent-400 mt-1">&#8226;</span>
                      {item}
                    </li>
                  ))}
                </ul>
              ) : typeof briefing.attendee_context === "string" ? (
                <p>{briefing.attendee_context as string}</p>
              ) : (
                <pre className="text-xs bg-surface-overlay rounded-xl p-4 overflow-x-auto">
                  {JSON.stringify(briefing.attendee_context, null, 2)}
                </pre>
              )}
            </div>
          </section>
        ) : null}

        {briefing.action_items_context != null ? (
          <section className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <ListChecks size={18} className="text-accent-500" />
              <h2 className="text-lg font-semibold text-text-primary">
                Related Action Items
              </h2>
            </div>
            <div className="text-sm text-text-secondary">
              {Array.isArray(briefing.action_items_context) ? (
                <ul className="space-y-2">
                  {(briefing.action_items_context as string[]).map(
                    (item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-accent-400 mt-1">&#8226;</span>
                        {item}
                      </li>
                    )
                  )}
                </ul>
              ) : typeof briefing.action_items_context === "string" ? (
                <p>{briefing.action_items_context as string}</p>
              ) : (
                <pre className="text-xs bg-surface-overlay rounded-xl p-4 overflow-x-auto">
                  {JSON.stringify(briefing.action_items_context, null, 2)}
                </pre>
              )}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
