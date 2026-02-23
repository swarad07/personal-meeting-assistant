"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { format, parseISO, differenceInMinutes } from "date-fns";
import { toast } from "sonner";
import {
  ArrowLeft,
  Clock,
  Users,
  MapPin,
  ExternalLink,
  Timer,
  CalendarDays,
  Sparkles,
  Loader2,
  FileText,
  BrainCircuit,
  History,
} from "lucide-react";
import { getInitials } from "@/lib/utils";

export default function CalendarEventDetailPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = use(params);
  const queryClient = useQueryClient();
  const [similarMeetings, setSimilarMeetings] = useState<
    { id: string; title: string; date: string }[]
  >([]);

  const {
    data: event,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["calendar-event", eventId],
    queryFn: () => api.calendar.event(eventId),
  });

  const { data: profilesData } = useQuery({
    queryKey: ["profiles-for-event"],
    queryFn: () => api.profiles.list(1, 500),
  });

  const briefingMutation = useMutation({
    mutationFn: () => api.calendar.generateBriefing(eventId),
    onMutate: () => {
      toast.loading("Generating briefing...", { id: "gen-briefing" });
    },
    onSuccess: (data) => {
      if (data.status === "success") {
        toast.success("Briefing generated", { id: "gen-briefing" });
        if (data.similar_meetings) {
          setSimilarMeetings(data.similar_meetings);
        }
      } else {
        toast.error("Could not generate briefing", { id: "gen-briefing" });
      }
      queryClient.invalidateQueries({ queryKey: ["calendar-event", eventId] });
    },
    onError: (err) => {
      toast.error(
        (err as Error).message || "Failed to generate briefing",
        { id: "gen-briefing" },
      );
    },
  });

  const emailToProfile = (() => {
    const map = new Map<string, { id: string; type: string }>();
    if (profilesData?.items) {
      for (const p of profilesData.items) {
        if (p.email) map.set(p.email.toLowerCase(), { id: p.id, type: p.type });
      }
    }
    return map;
  })();

  const selfEmail = profilesData?.items?.find((p) => p.type === "self")?.email?.toLowerCase();

  const resolveAttendeeLink = (email: string | null): string | null => {
    if (!email) return null;
    const lower = email.toLowerCase();
    if (lower === selfEmail) return "/profiles/me";
    const match = emailToProfile.get(lower);
    return match ? `/profiles/${match.id}` : null;
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <div className="h-8 w-48 rounded-xl shimmer mb-6" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-2xl shimmer" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <Link
          href="/meetings"
          className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
        >
          <ArrowLeft size={14} /> Back to Meetings
        </Link>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error ? (error as Error).message : "Event not found"}
        </div>
      </div>
    );
  }

  const start = parseISO(event.start);
  const end = parseISO(event.end);
  const durationMin = differenceInMinutes(end, start);
  const hasBriefing = !!event.briefing;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link
        href="/meetings"
        className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
      >
        <ArrowLeft size={14} /> Back to Meetings
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold tracking-tight text-text-primary">
                {event.title}
              </h1>
              <span className="badge badge-info text-[10px] gap-1 shrink-0">
                <CalendarDays size={9} />
                Upcoming
              </span>
              {hasBriefing && (
                <span className="badge badge-success text-[10px] gap-1 shrink-0">
                  <FileText size={9} />
                  Briefing ready
                </span>
              )}
            </div>

            <div className="mt-3 flex items-center gap-5 text-sm text-text-muted flex-wrap">
              <span className="flex items-center gap-1.5">
                <CalendarDays size={14} />
                {format(start, "EEEE, MMMM d, yyyy")}
              </span>
              <span className="flex items-center gap-1.5">
                <Clock size={14} />
                {format(start, "h:mm a")} – {format(end, "h:mm a")}
              </span>
              {durationMin > 0 && (
                <span className="flex items-center gap-1.5">
                  <Timer size={14} />
                  {durationMin} min
                </span>
              )}
            </div>
          </div>

          <button
            className="btn-gradient flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-60"
            onClick={() => briefingMutation.mutate()}
            disabled={briefingMutation.isPending}
          >
            {briefingMutation.isPending ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <BrainCircuit size={16} />
            )}
            {hasBriefing ? "Regenerate Briefing" : "Generate Briefing"}
          </button>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Briefing */}
          {hasBriefing ? (
            <section className="glass-card p-6">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-text-primary mb-4">
                <Sparkles size={18} className="text-accent-500" />
                Meeting Briefing
              </h2>
              <div className="prose prose-sm max-w-none text-text-secondary whitespace-pre-wrap leading-relaxed">
                {event.briefing!.content}
              </div>
              {event.briefing!.topics && event.briefing!.topics.length > 0 && (
                <div className="mt-5 pt-4 border-t border-border-subtle">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
                    Key Topics
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {event.briefing!.topics.map((topic, i) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 text-xs rounded-full bg-accent-50 text-accent-700 border border-accent-200"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </section>
          ) : (
            <section className="glass-card p-10 text-center">
              <BrainCircuit
                size={48}
                className="mx-auto mb-4 text-text-muted opacity-40"
              />
              <h2 className="text-lg font-semibold text-text-primary mb-2">
                No Briefing Yet
              </h2>
              <p className="text-sm text-text-muted mb-5 max-w-md mx-auto">
                Generate an AI briefing to get an overview of likely discussion
                topics, attendee context, open action items, and preparation
                suggestions based on similar past meetings.
              </p>
              <button
                className="btn-gradient inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-60"
                onClick={() => briefingMutation.mutate()}
                disabled={briefingMutation.isPending}
              >
                {briefingMutation.isPending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                Generate Briefing
              </button>
            </section>
          )}

          {/* Similar past meetings */}
          {similarMeetings.length > 0 && (
            <section className="glass-card p-6">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-text-primary mb-4">
                <History size={18} className="text-accent-500" />
                Related Past Meetings
              </h2>
              <div className="space-y-2">
                {similarMeetings.map((m) => (
                  <Link
                    key={m.id}
                    href={`/meetings/${m.id}`}
                    className="flex items-center justify-between p-3 rounded-xl hover:bg-surface-overlay/50 transition-colors group"
                  >
                    <span className="text-sm font-medium text-text-primary group-hover:text-accent-600 transition-colors truncate">
                      {m.title}
                    </span>
                    {m.date && (
                      <span className="text-xs text-text-muted shrink-0 ml-3">
                        {format(parseISO(m.date), "MMM d, yyyy")}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Attendees */}
          {event.attendees.length > 0 && (
            <section className="glass-card p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-3">
                <Users size={15} className="text-accent-500" />
                Attendees ({event.attendees.length})
              </h3>
              <div className="space-y-2">
                {event.attendees.map((att, i) => {
                  const displayName =
                    att.name || att.email?.split("@")[0] || "Unknown";
                  const link = resolveAttendeeLink(att.email);
                  const inner = (
                    <div className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-surface-overlay/50 transition-colors">
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
                        {getInitials(displayName)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text-primary truncate">
                          {displayName}
                        </p>
                        {att.email && att.email !== att.name && (
                          <p className="text-xs text-text-muted truncate">
                            {att.email}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                  return link ? (
                    <Link
                      key={att.email ?? i}
                      href={link}
                      className="block"
                    >
                      {inner}
                    </Link>
                  ) : (
                    <div key={att.email ?? i}>{inner}</div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Event details */}
          <section className="glass-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-text-primary">
              Event Details
            </h3>

            {event.location && (
              <div className="flex items-start gap-2 text-sm">
                <MapPin
                  size={14}
                  className="text-text-muted mt-0.5 shrink-0"
                />
                <span className="text-text-secondary">{event.location}</span>
              </div>
            )}

            {event.description && (
              <div className="text-sm text-text-secondary border-t border-border-subtle pt-3">
                <p className="whitespace-pre-wrap line-clamp-6">
                  {event.description}
                </p>
              </div>
            )}

            {event.html_link && (
              <a
                href={event.html_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 transition-colors font-medium"
              >
                <ExternalLink size={14} />
                Open in Google Calendar
              </a>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
