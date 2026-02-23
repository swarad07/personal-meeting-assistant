"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { format, isToday, isYesterday, isTomorrow, parseISO, differenceInMinutes } from "date-fns";
import {
  MessageSquare,
  Users,
  Clock,
  CheckSquare,
  Cloud,
  Database,
  Loader2,
  Timer,
  CalendarDays,
  History,
  MapPin,
  ExternalLink,
  FileText,
  CalendarOff,
} from "lucide-react";
import { getInitials } from "@/lib/utils";
import type { Meeting, CalendarEvent } from "@/lib/types";

type Tab = "past" | "upcoming";

const PAGE_SIZE = 30;
const DAY_OPTIONS = [7, 14, 30] as const;

function formatDateHeading(dateStr: string): string {
  const d = parseISO(dateStr);
  if (isToday(d)) return "Today";
  if (isYesterday(d)) return "Yesterday";
  if (isTomorrow(d)) return "Tomorrow";
  return format(d, "EEEE, MMMM d, yyyy");
}

function dateKey(dateStr: string): string {
  return dateStr.slice(0, 10);
}

function groupByDate(meetings: Meeting[]): { date: string; label: string; meetings: Meeting[] }[] {
  const groups = new Map<string, Meeting[]>();
  for (const m of meetings) {
    const key = dateKey(m.date);
    const existing = groups.get(key);
    if (existing) {
      existing.push(m);
    } else {
      groups.set(key, [m]);
    }
  }
  return Array.from(groups.entries()).map(([key, items]) => ({
    date: key,
    label: formatDateHeading(items[0].date),
    meetings: items,
  }));
}

function groupEventsByDate(events: CalendarEvent[]): { date: string; label: string; events: CalendarEvent[] }[] {
  const groups = new Map<string, CalendarEvent[]>();
  for (const e of events) {
    const key = dateKey(e.start);
    const existing = groups.get(key);
    if (existing) {
      existing.push(e);
    } else {
      groups.set(key, [e]);
    }
  }
  return Array.from(groups.entries()).map(([key, items]) => ({
    date: key,
    label: formatDateHeading(items[0].start),
    events: items,
  }));
}

export default function MeetingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("past");

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">
            Meetings
          </h1>
        </div>
      </div>

      <div className="tab-pills mb-6">
        <button
          onClick={() => setActiveTab("past")}
          className={`tab-pill ${activeTab === "past" ? "tab-pill-active" : ""}`}
        >
          <History size={14} />
          Past Meetings
        </button>
        <button
          onClick={() => setActiveTab("upcoming")}
          className={`tab-pill ${activeTab === "upcoming" ? "tab-pill-active" : ""}`}
        >
          <CalendarDays size={14} />
          Upcoming
        </button>
      </div>

      {activeTab === "past" && <PastMeetings />}
      {activeTab === "upcoming" && <UpcomingMeetings />}
    </div>
  );
}

/* ── Past Meetings (existing infinite scroll) ──────────────────────── */

function PastMeetings() {
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["meetings-infinite"],
    queryFn: ({ pageParam = 1 }) => api.meetings.list(pageParam, PAGE_SIZE),
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, p) => n + p.items.length, 0);
      return loaded < lastPage.total ? allPages.length + 1 : undefined;
    },
    initialPageParam: 1,
  });

  const sentinelRef = useRef<HTMLDivElement>(null);

  const handleIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [fetchNextPage, hasNextPage, isFetchingNextPage],
  );

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(handleIntersect, {
      rootMargin: "400px",
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [handleIntersect]);

  const allMeetings = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );
  const totalCount = data?.pages[0]?.total ?? 0;
  const dateGroups = useMemo(() => groupByDate(allMeetings), [allMeetings]);

  return (
    <>
      <p className="text-sm text-text-muted mb-6">
        {totalCount > 0
          ? `${totalCount} meetings synced`
          : isLoading
            ? "Loading..."
            : "No meetings yet"}
      </p>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-2xl shimmer" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load meetings: {(error as Error).message}
        </div>
      )}

      {dateGroups.length > 0 && (
        <div className="space-y-8">
          {dateGroups.map((group) => (
            <section key={group.date}>
              <div className="section-header py-2">
                <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                  {group.label}
                  <span className="ml-2 font-normal normal-case text-text-muted/70">
                    ({group.meetings.length})
                  </span>
                </h2>
              </div>

              <div className="space-y-2.5 mt-3">
                {group.meetings.map((meeting) => (
                  <MeetingCard key={meeting.id} meeting={meeting} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {allMeetings.length === 0 && !isLoading && !error && (
        <div className="empty-state">
          <div className="icon-box icon-box-lg icon-box-indigo mx-auto">
            <MessageSquare size={22} />
          </div>
          <p className="mt-4 text-sm font-medium text-text-secondary">
            No meetings yet
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Connect Granola to start syncing your meetings.
          </p>
        </div>
      )}

      <div ref={sentinelRef} className="h-1" />

      {isFetchingNextPage && (
        <div className="flex justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-accent-400" />
        </div>
      )}

      {!hasNextPage && allMeetings.length > 0 && (
        <p className="text-center text-xs text-text-muted py-6">
          All {totalCount} meetings loaded
        </p>
      )}
    </>
  );
}

/* ── Upcoming Meetings (Google Calendar) ───────────────────────────── */

function UpcomingMeetings() {
  const [days, setDays] = useState<number>(7);

  const { data, isLoading, error } = useQuery({
    queryKey: ["calendar-events", days],
    queryFn: () => api.calendar.events(days),
    retry: false,
  });

  const isDisconnected =
    error && (error as Error).message?.includes("503");

  const events = data?.events ?? [];
  const eventGroups = useMemo(() => groupEventsByDate(events), [events]);

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-text-muted">
          {isLoading
            ? "Loading..."
            : isDisconnected
              ? "Google Calendar not connected"
              : `${events.length} event${events.length !== 1 ? "s" : ""} in the next ${days} days`}
        </p>

        {!isDisconnected && (
          <div className="tab-pills">
            {DAY_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => setDays(opt)}
                className={`tab-pill !px-3 !py-1.5 !text-xs ${days === opt ? "tab-pill-active" : ""}`}
              >
                {opt}d
              </button>
            ))}
          </div>
        )}
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 rounded-2xl shimmer" />
          ))}
        </div>
      )}

      {isDisconnected && (
        <div className="empty-state">
          <div className="icon-box icon-box-lg icon-box-amber mx-auto">
            <CalendarOff size={22} />
          </div>
          <p className="mt-4 text-sm font-medium text-text-secondary">
            Google Calendar not connected
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Connect your Google Calendar in Settings to see upcoming meetings.
          </p>
          <Link
            href="/settings"
            className="mt-4 inline-flex items-center gap-1.5 rounded-xl gradient-bg px-5 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-lg shadow-accent-500/25"
          >
            Go to Settings
          </Link>
        </div>
      )}

      {error && !isDisconnected && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load calendar events: {(error as Error).message}
        </div>
      )}

      {eventGroups.length > 0 && (
        <div className="space-y-8">
          {eventGroups.map((group) => (
            <section key={group.date}>
              <div className="section-header py-2">
                <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                  {group.label}
                  <span className="ml-2 font-normal normal-case text-text-muted/70">
                    ({group.events.length})
                  </span>
                </h2>
              </div>

              <div className="space-y-2.5 mt-3">
                {group.events.map((event) => (
                  <EventCard key={event.event_id} event={event} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {events.length === 0 && !isLoading && !error && (
        <div className="empty-state">
          <div className="icon-box icon-box-lg icon-box-violet mx-auto">
            <CalendarDays size={22} />
          </div>
          <p className="mt-4 text-sm font-medium text-text-secondary">
            No upcoming events
          </p>
          <p className="mt-1 text-xs text-text-muted">
            No events in the next {days} days.
          </p>
        </div>
      )}
    </>
  );
}

/* ── Cards ─────────────────────────────────────────────────────────── */

function MeetingCard({ meeting }: { meeting: Meeting }) {
  return (
    <Link
      href={`/meetings/${meeting.id}`}
      className="block glass-card card-accent p-5 pl-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <h3 className="text-base font-semibold text-text-primary truncate">
              {meeting.title}
            </h3>
            {meeting.sync_source && (
              <span
                className={`badge text-[10px] gap-1 shrink-0 ${
                  meeting.sync_source === "mcp"
                    ? "badge-info"
                    : "badge-neutral"
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
          {meeting.summary && (
            <p className="mt-1.5 text-sm text-text-secondary line-clamp-2">
              {meeting.summary}
            </p>
          )}
          <div className="mt-3 flex items-center gap-4 text-xs text-text-muted">
            <span className="flex items-center gap-1">
              <Clock size={12} className="text-accent-400" />
              {format(parseISO(meeting.date), "h:mm a")}
            </span>
            {meeting.duration && (
              <span className="flex items-center gap-1">
                <Timer size={12} className="text-cyan-400" />
                {meeting.duration} min
              </span>
            )}
            {meeting.attendees.length > 0 && (
              <span className="flex items-center gap-1">
                <Users size={12} className="text-violet-400" />
                {meeting.attendees.length}
              </span>
            )}
            {meeting.action_items_count > 0 && (
              <span className="flex items-center gap-1 text-emerald-600 font-medium">
                <CheckSquare size={12} />
                {meeting.action_items_count} actions
              </span>
            )}
          </div>
        </div>
        <div className="flex -space-x-1.5 shrink-0">
          {meeting.attendees.slice(0, 4).map((a, i) => (
            <div
              key={a.id}
              className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-white text-[10px] font-semibold text-white shadow-sm"
              style={{
                background: [
                  "linear-gradient(135deg, #6366f1, #818cf8)",
                  "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                  "linear-gradient(135deg, #06b6d4, #22d3ee)",
                  "linear-gradient(135deg, #f59e0b, #fbbf24)",
                ][i % 4],
              }}
              title={a.name}
            >
              {getInitials(a.name)}
            </div>
          ))}
          {meeting.attendees.length > 4 && (
            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-surface-overlay text-[10px] font-semibold text-text-muted">
              +{meeting.attendees.length - 4}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}

function EventCard({ event }: { event: CalendarEvent }) {
  const start = parseISO(event.start);
  const end = parseISO(event.end);
  const durationMin = differenceInMinutes(end, start);

  return (
    <Link href={`/calendar/${event.event_id}`} className="block glass-card card-accent p-5 pl-6 cursor-pointer">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-text-primary truncate">
              {event.title}
            </h3>
            {event.briefing && (
              <span className="badge badge-success text-[10px] gap-1 shrink-0">
                <FileText size={9} />
                Briefing ready
              </span>
            )}
          </div>

          {event.description && (
            <p className="mt-1.5 text-sm text-text-secondary line-clamp-2">
              {event.description}
            </p>
          )}

          <div className="mt-3 flex items-center gap-4 text-xs text-text-muted flex-wrap">
            <span className="flex items-center gap-1">
              <Clock size={13} />
              {format(start, "h:mm a")} – {format(end, "h:mm a")}
            </span>
            {durationMin > 0 && (
              <span className="flex items-center gap-1">
                <Timer size={13} />
                {durationMin} min
              </span>
            )}
            {event.location && (
              <span className="flex items-center gap-1">
                <MapPin size={13} />
                <span className="truncate max-w-[200px]">{event.location}</span>
              </span>
            )}
            {event.attendees.length > 0 && (
              <span className="flex items-center gap-1">
                <Users size={13} />
                {event.attendees.length}
              </span>
            )}
            {event.html_link && (
              <a
                href={event.html_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-accent-500 hover:text-accent-700 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink size={13} />
                Google Calendar
              </a>
            )}
          </div>
        </div>

        <div className="flex -space-x-1.5 shrink-0">
          {event.attendees.slice(0, 4).map((a, i) => (
            <div
              key={a.email ?? i}
              className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-white text-[10px] font-semibold text-white"
              style={{
                background: [
                  "linear-gradient(135deg, #6366f1, #818cf8)",
                  "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                  "linear-gradient(135deg, #06b6d4, #22d3ee)",
                  "linear-gradient(135deg, #f59e0b, #fbbf24)",
                ][i % 4],
              }}
              title={a.name || a.email || "Attendee"}
            >
              {getInitials(a.name || a.email?.split("@")[0] || "?")}
            </div>
          ))}
          {event.attendees.length > 4 && (
            <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-white bg-surface-overlay text-[10px] font-semibold text-text-muted">
              +{event.attendees.length - 4}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
