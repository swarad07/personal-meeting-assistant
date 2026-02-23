"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { format } from "date-fns";
import { toast } from "sonner";
import {
  ArrowLeft,
  Clock,
  Users,
  FileText,
  MessageCircle,
  CheckSquare,
  Cloud,
  Database,
  ChevronDown,
  ChevronRight,
  Timer,
  CalendarDays,
  RefreshCw,
  Sparkles,
  Loader2,
  BrainCircuit,
} from "lucide-react";
import { getInitials } from "@/lib/utils";

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function computeDurationFromTranscript(
  chunks: { start_time: number | null; end_time: number | null }[]
): number | null {
  const times = chunks.flatMap((c) =>
    [c.start_time, c.end_time].filter((t): t is number => t !== null)
  );
  if (times.length < 2) return null;
  const delta = (Math.max(...times) - Math.min(...times)) / 60;
  return delta > 0 ? Math.round(delta) : null;
}

export default function MeetingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const queryClient = useQueryClient();

  const {
    data: meeting,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["meeting", id],
    queryFn: () => api.meetings.get(id),
  });

  const resyncMutation = useMutation({
    mutationFn: () => api.meetings.resync(id),
    onMutate: () => {
      toast.loading("Pulling notes from Granola...", { id: "resync" });
    },
    onSuccess: (data) => {
      if (data.status === "success") {
        const parts: string[] = [];
        if (data.has_notes) parts.push("notes");
        if (data.transcript_chunks) parts.push(`${data.transcript_chunks} transcript segments`);
        toast.success(
          parts.length ? `Pulled ${parts.join(", ")}` : "Meeting re-synced",
          { id: "resync" },
        );
      } else {
        toast.error("Re-sync returned no data", { id: "resync" });
      }
      queryClient.invalidateQueries({ queryKey: ["meeting", id] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to pull notes", { id: "resync" });
    },
  });

  const summaryMutation = useMutation({
    mutationFn: () => api.meetings.generateSummary(id),
    onMutate: () => {
      toast.loading("Generating summary...", { id: "gen-summary" });
    },
    onSuccess: (data) => {
      if (data.status === "success") {
        toast.success("Summary generated", { id: "gen-summary" });
      } else if (data.status === "skipped") {
        toast.info(data.reason || "Nothing to summarize", { id: "gen-summary" });
      } else {
        toast.error(data.reason || "Summary generation failed", { id: "gen-summary" });
      }
      queryClient.invalidateQueries({ queryKey: ["meeting", id] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to generate summary", { id: "gen-summary" });
    },
  });

  const actionItemMutation = useMutation({
    mutationFn: ({ id: itemId, status }: { id: string; status: string }) =>
      api.actionItems.update(itemId, { status }),
    onSuccess: (_, { status }) => {
      toast.success(status === "done" ? "Marked as done" : status === "dismissed" ? "Dismissed" : "Reopened");
      queryClient.invalidateQueries({ queryKey: ["meeting", id] });
      queryClient.invalidateQueries({ queryKey: ["actionItems"] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to update action item");
    },
  });

  const briefMutation = useMutation({
    mutationFn: () => api.meetings.generateBrief(id),
    onMutate: () => {
      toast.loading("Generating next-call brief...", { id: "gen-brief" });
    },
    onSuccess: (data) => {
      if (data.status === "success" && data.brief) {
        toast.success("Brief generated", { id: "gen-brief" });
      } else {
        toast.error("Could not generate brief", { id: "gen-brief" });
      }
      queryClient.invalidateQueries({ queryKey: ["meeting", id] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to generate brief", { id: "gen-brief" });
    },
  });

  const { data: profilesData } = useQuery({
    queryKey: ["profiles-for-meeting"],
    queryFn: () => api.profiles.list(1, 500),
  });

  const findProfileId = (name: string, email: string | null): string | undefined => {
    if (!profilesData?.items) return undefined;
    for (const p of profilesData.items) {
      if (p.name.toLowerCase() === name.toLowerCase()) return p.id;
      if (email && p.email && p.email.toLowerCase() === email.toLowerCase()) return p.id;
    }
    const nameLower = name.toLowerCase();
    for (const p of profilesData.items) {
      if (p.name.toLowerCase().includes(nameLower) || nameLower.includes(p.name.toLowerCase())) return p.id;
    }
    return undefined;
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="h-8 w-48 rounded-xl shimmer mb-6" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-2xl shimmer" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <Link
          href="/meetings"
          className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
        >
          <ArrowLeft size={14} /> Back to Meetings
        </Link>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error ? (error as Error).message : "Meeting not found"}
        </div>
      </div>
    );
  }

  const duration =
    meeting.duration ??
    computeDurationFromTranscript(meeting.transcript_chunks);

  const hasNotes = !!(meeting.raw_notes || meeting.enhanced_notes);
  const hasSummary = !!meeting.summary;
  const hasBrief = !!meeting.next_call_brief;
  const hasTranscript = meeting.transcript_chunks.length > 0;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link
        href="/meetings"
        className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
      >
        <ArrowLeft size={14} /> Back to Meetings
      </Link>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              {meeting.title}
            </h1>
            {meeting.sync_source && (
              <span
                className={`badge text-[10px] gap-1 shrink-0 ${
                  meeting.sync_source === "mcp" ? "badge-info" : "badge-neutral"
                }`}
                title={
                  meeting.sync_source === "mcp"
                    ? "Synced via Granola Cloud API"
                    : "Synced from local cache"
                }
              >
                {meeting.sync_source === "mcp" ? (
                  <Cloud size={9} />
                ) : (
                  <Database size={9} />
                )}
                {meeting.sync_source === "mcp" ? "Cloud" : "Cache"}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
            <button
              onClick={() => resyncMutation.mutate()}
              disabled={resyncMutation.isPending}
              className="flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-overlay disabled:opacity-50 transition-all"
              title="Re-fetch notes and transcript from Granola"
            >
              {resyncMutation.isPending ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <RefreshCw size={13} />
              )}
              Pull Notes
            </button>
            <button
              onClick={() => summaryMutation.mutate()}
              disabled={summaryMutation.isPending}
              className="flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-xs font-medium text-text-secondary hover:bg-surface-overlay disabled:opacity-50 transition-all"
              title="Generate or regenerate AI summary"
            >
              {summaryMutation.isPending ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Sparkles size={13} />
              )}
              {hasSummary ? "Regenerate Summary" : "Generate Summary"}
            </button>
            <button
              onClick={() => briefMutation.mutate()}
              disabled={briefMutation.isPending}
              className="flex items-center gap-1.5 rounded-xl gradient-bg px-3 py-2 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
              title="Generate a prep brief for next call with these attendees"
            >
              {briefMutation.isPending ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <BrainCircuit size={13} />
              )}
              {hasBrief ? "Regenerate Brief" : "Next Call Brief"}
            </button>
          </div>
        </div>

        {/* Metadata chips */}
        <div className="mt-3 flex items-center gap-3 flex-wrap text-sm text-text-muted">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-secondary/60 px-2.5 py-1">
            <CalendarDays size={13} className="text-accent-400" />
            {format(new Date(meeting.date), "EEEE, MMM d, yyyy")}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-secondary/60 px-2.5 py-1">
            <Clock size={13} className="text-accent-400" />
            {format(new Date(meeting.date), "h:mm a")}
          </span>
          {duration && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-secondary/60 px-2.5 py-1">
              <Timer size={13} className="text-accent-400" />
              {formatDuration(duration)}
            </span>
          )}
          {meeting.attendees.length > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-secondary/60 px-2.5 py-1">
              <Users size={13} className="text-accent-400" />
              {meeting.attendees.length} attendee
              {meeting.attendees.length !== 1 && "s"}
            </span>
          )}
          {hasTranscript && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-secondary/60 px-2.5 py-1">
              <MessageCircle size={13} className="text-accent-400" />
              {meeting.transcript_chunks.length} segments
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ── Main column ──────────────────────────────────── */}
        <div className="space-y-6 lg:col-span-2">
          {/* Summary — always first */}
          {hasSummary && (
            <section className="glass-card p-6">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                <FileText size={15} className="text-accent-400" /> Summary
              </h2>
              <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
                {meeting.summary}
              </p>
            </section>
          )}

          {/* Next Call Brief */}
          {meeting.next_call_brief && (
            <section className="glass-card p-6 border border-accent-200/50 bg-gradient-to-br from-accent-50/30 to-purple-50/30">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                <BrainCircuit size={15} className="text-accent-500" /> Next Call Brief
              </h2>
              <div
                className="prose prose-sm max-w-none text-text-secondary"
                dangerouslySetInnerHTML={{
                  __html: meeting.next_call_brief
                    .replace(
                      /^#{1,3} (.+)$/gm,
                      '<h3 class="text-sm font-semibold text-text-primary mt-4 mb-1">$1</h3>'
                    )
                    .replace(
                      /\*\*(.+?)\*\*/g,
                      '<strong class="text-text-primary">$1</strong>'
                    )
                    .replace(
                      /^- (.+)$/gm,
                      '<li class="ml-4 list-disc text-sm text-text-secondary">$1</li>'
                    )
                    .replace(
                      /^\d+\. (.+)$/gm,
                      '<li class="ml-4 list-decimal text-sm text-text-secondary">$1</li>'
                    )
                    .replace(/\n\n/g, "<br/>"),
                }}
              />
            </section>
          )}

          {/* Notes */}
          {hasNotes && (
            <section className="glass-card p-6">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                <FileText size={15} className="text-accent-400" /> Notes
              </h2>
              {meeting.enhanced_notes ? (
                <div
                  className="prose prose-sm max-w-none text-text-secondary"
                  dangerouslySetInnerHTML={{
                    __html: meeting.enhanced_notes
                      .replace(
                        /^### (.+)$/gm,
                        '<h3 class="text-sm font-medium text-text-primary mt-4 mb-1">$1</h3>'
                      )
                      .replace(
                        /^## (.+)$/gm,
                        '<h2 class="text-sm font-semibold text-text-primary mt-5 mb-2">$1</h2>'
                      )
                      .replace(
                        /^- (.+)$/gm,
                        '<li class="ml-4 list-disc text-sm text-text-secondary">$1</li>'
                      )
                      .replace(/\n\n/g, "<br/>"),
                  }}
                />
              ) : (
                <p className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">
                  {meeting.raw_notes}
                </p>
              )}
            </section>
          )}

          {/* Transcript — collapsible */}
          {hasTranscript && (
            <section className="glass-card overflow-hidden">
              <button
                onClick={() => setTranscriptOpen((o) => !o)}
                className="w-full flex items-center justify-between p-6 text-left hover:bg-surface-secondary/30 transition-colors"
              >
                <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary uppercase tracking-wide">
                  <MessageCircle size={15} className="text-accent-400" />{" "}
                  Transcript
                  <span className="text-text-muted font-normal normal-case text-xs">
                    ({meeting.transcript_chunks.length} segments)
                  </span>
                </h2>
                {transcriptOpen ? (
                  <ChevronDown size={16} className="text-text-muted" />
                ) : (
                  <ChevronRight size={16} className="text-text-muted" />
                )}
              </button>

              {transcriptOpen && (
                <div className="px-6 pb-6 space-y-3 border-t border-border-primary/40 pt-4 max-h-[60vh] overflow-y-auto">
                  {meeting.transcript_chunks.map((chunk, i) => (
                    <div key={chunk.id} className="flex gap-3">
                      {chunk.speaker && (
                        <div
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white mt-0.5"
                          style={{
                            background: [
                              "linear-gradient(135deg, #6366f1, #818cf8)",
                              "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                              "linear-gradient(135deg, #06b6d4, #22d3ee)",
                              "linear-gradient(135deg, #f59e0b, #fbbf24)",
                            ][i % 4],
                          }}
                        >
                          {getInitials(chunk.speaker)}
                        </div>
                      )}
                      <div className="min-w-0">
                        {chunk.speaker && (
                          <span className="text-xs font-semibold text-text-primary">
                            {chunk.speaker}
                          </span>
                        )}
                        <p className="text-sm text-text-secondary leading-relaxed">
                          {chunk.content}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Empty state when no content at all */}
          {!hasSummary && !hasNotes && !hasTranscript && (
            <div className="glass-card p-8 text-center">
              <FileText
                size={32}
                className="mx-auto mb-3 text-text-muted/40"
              />
              <p className="text-sm text-text-muted">
                No summary, notes, or transcript available for this meeting.
              </p>
            </div>
          )}
        </div>

        {/* ── Sidebar ──────────────────────────────────────── */}
        <div className="space-y-6">
          {/* Attendees */}
          {meeting.attendees.length > 0 && (
            <section className="glass-card p-6">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                <Users size={15} className="text-accent-400" /> Attendees
                <span className="text-text-muted font-normal normal-case text-xs">
                  ({meeting.attendees.length})
                </span>
              </h2>
              <ul className="space-y-1">
                {meeting.attendees.map((a, i) => {
                  const profileId = findProfileId(a.name, a.email);

                  return (
                    <li key={a.id}>
                      {profileId ? (
                        <Link
                          href={`/profiles/${profileId}`}
                          className="flex items-center gap-2.5 rounded-lg -mx-2 px-2 py-1.5 hover:bg-accent-50/50 transition-colors group"
                        >
                          <div
                            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white"
                            style={{
                              background: [
                                "linear-gradient(135deg, #6366f1, #818cf8)",
                                "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                                "linear-gradient(135deg, #06b6d4, #22d3ee)",
                                "linear-gradient(135deg, #f59e0b, #fbbf24)",
                              ][i % 4],
                            }}
                          >
                            {getInitials(a.name)}
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-accent-600 group-hover:text-accent-700 truncate">
                              {a.name}
                            </p>
                            {a.role && (
                              <p className="text-xs text-text-muted truncate">
                                {a.role}
                              </p>
                            )}
                          </div>
                        </Link>
                      ) : (
                        <div className="flex items-center gap-2.5 px-2 py-1.5 -mx-2">
                          <div
                            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white"
                            style={{
                              background: [
                                "linear-gradient(135deg, #6366f1, #818cf8)",
                                "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                                "linear-gradient(135deg, #06b6d4, #22d3ee)",
                                "linear-gradient(135deg, #f59e0b, #fbbf24)",
                              ][i % 4],
                            }}
                          >
                            {getInitials(a.name)}
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-text-primary truncate">
                              {a.name}
                            </p>
                            {a.role && (
                              <p className="text-xs text-text-muted truncate">
                                {a.role}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {/* Action Items */}
          {meeting.action_items.length > 0 && (
            <section className="glass-card p-6">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
                <CheckSquare size={15} className="text-accent-400" /> Action
                Items
                <span className="text-text-muted font-normal normal-case text-xs">
                  ({meeting.action_items.length})
                </span>
              </h2>
              <ul className="space-y-2.5">
                {meeting.action_items.map((ai) => (
                  <li key={ai.id} className="flex items-start gap-2">
                    <button
                      onClick={() =>
                        actionItemMutation.mutate({
                          id: ai.id,
                          status: ai.status === "done" ? "open" : "done",
                        })
                      }
                      className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-md border-2 transition-all ${
                        ai.status === "done"
                          ? "border-emerald-500 bg-emerald-500 text-white"
                          : "border-accent-300 hover:border-accent-400"
                      }`}
                      title={ai.status === "done" ? "Mark as open" : "Mark as done"}
                    >
                      {ai.status === "done" && <CheckSquare size={10} />}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-sm ${
                          ai.status === "done"
                            ? "text-text-muted line-through"
                            : "text-text-primary"
                        }`}
                      >
                        {ai.description}
                      </p>
                      {ai.assignee && (
                        <p className="text-xs text-text-muted mt-0.5">
                          {ai.assignee}
                        </p>
                      )}
                    </div>
                    {ai.status === "open" && (
                      <button
                        onClick={() =>
                          actionItemMutation.mutate({
                            id: ai.id,
                            status: "dismissed",
                          })
                        }
                        className="text-[10px] text-text-muted hover:text-red-500 transition-colors font-medium mt-0.5 shrink-0"
                      >
                        Dismiss
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Meeting Info */}
          <section className="glass-card p-6">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3 uppercase tracking-wide">
              <CalendarDays size={15} className="text-accent-400" /> Details
            </h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-text-muted">Date</dt>
                <dd className="text-text-primary font-medium">
                  {format(new Date(meeting.date), "MMM d, yyyy")}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">Time</dt>
                <dd className="text-text-primary font-medium">
                  {format(new Date(meeting.date), "h:mm a")}
                </dd>
              </div>
              {duration && (
                <div className="flex justify-between">
                  <dt className="text-text-muted">Duration</dt>
                  <dd className="text-text-primary font-medium">
                    {formatDuration(duration)}
                  </dd>
                </div>
              )}
              {meeting.synced_at && (
                <div className="flex justify-between">
                  <dt className="text-text-muted">Last synced</dt>
                  <dd className="text-text-primary font-medium">
                    {format(new Date(meeting.synced_at), "MMM d, h:mm a")}
                  </dd>
                </div>
              )}
              {meeting.sync_source && (
                <div className="flex justify-between">
                  <dt className="text-text-muted">Source</dt>
                  <dd className="text-text-primary font-medium inline-flex items-center gap-1">
                    {meeting.sync_source === "mcp" ? (
                      <Cloud size={12} className="text-blue-500" />
                    ) : (
                      <Database size={12} className="text-gray-400" />
                    )}
                    {meeting.sync_source === "mcp" ? "Cloud API" : "Local cache"}
                  </dd>
                </div>
              )}
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}
