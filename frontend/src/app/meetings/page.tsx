"use client";

import { useCallback, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { format, isToday, isYesterday, parseISO } from "date-fns";
import {
  MessageSquare,
  Users,
  Clock,
  CheckSquare,
  Cloud,
  Database,
  Loader2,
  Timer,
} from "lucide-react";
import { getInitials } from "@/lib/utils";
import type { Meeting } from "@/lib/types";

const PAGE_SIZE = 30;

function formatDateHeading(dateStr: string): string {
  const d = parseISO(dateStr);
  if (isToday(d)) return "Today";
  if (isYesterday(d)) return "Yesterday";
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

export default function MeetingsPage() {
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
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">
            Meetings
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {totalCount > 0
              ? `${totalCount} meetings synced`
              : isLoading
                ? "Loading..."
                : "No meetings yet"}
          </p>
        </div>
      </div>

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
              <div className="py-2">
                <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wide">
                  {group.label}
                  <span className="ml-2 text-xs font-normal normal-case">
                    ({group.meetings.length} meeting{group.meetings.length !== 1 && "s"})
                  </span>
                </h2>
              </div>

              <div className="space-y-2 mt-2">
                {group.meetings.map((meeting) => (
                  <MeetingCard key={meeting.id} meeting={meeting} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {allMeetings.length === 0 && !isLoading && !error && (
        <div className="rounded-2xl border-2 border-dashed border-border p-12 text-center">
          <MessageSquare className="mx-auto h-10 w-10 text-text-muted" />
          <p className="mt-3 text-sm text-text-muted">
            No meetings yet. Connect Granola to start syncing.
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
    </div>
  );
}

function MeetingCard({ meeting }: { meeting: Meeting }) {
  return (
    <Link
      href={`/meetings/${meeting.id}`}
      className="block glass-card p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
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
              <Clock size={13} />
              {format(parseISO(meeting.date), "h:mm a")}
            </span>
            {meeting.duration && (
              <span className="flex items-center gap-1">
                <Timer size={13} />
                {meeting.duration} min
              </span>
            )}
            {meeting.attendees.length > 0 && (
              <span className="flex items-center gap-1">
                <Users size={13} />
                {meeting.attendees.length}
              </span>
            )}
            {meeting.action_items_count > 0 && (
              <span className="flex items-center gap-1 text-accent-500">
                <CheckSquare size={13} />
                {meeting.action_items_count} action items
              </span>
            )}
          </div>
        </div>
        <div className="flex -space-x-1.5 shrink-0">
          {meeting.attendees.slice(0, 4).map((a, i) => (
            <div
              key={a.id}
              className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-white text-[10px] font-semibold text-white"
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
