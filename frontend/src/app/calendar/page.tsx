"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Users,
  RefreshCw,
  FileText,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api-client";
import type { CalendarEvent } from "@/lib/types";

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);

  useEffect(() => {
    loadEvents();
  }, [days]);

  async function loadEvents() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.calendar.events(days);
      setEvents(data.events);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load calendar events"
      );
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      await api.calendar.sync();
      await loadEvents();
    } catch {
      // sync may fail if gcal not connected
    } finally {
      setSyncing(false);
    }
  }

  function groupByDate(
    eventList: CalendarEvent[]
  ): Record<string, CalendarEvent[]> {
    const groups: Record<string, CalendarEvent[]> = {};
    for (const event of eventList) {
      const dateKey = event.start
        ? new Date(event.start).toLocaleDateString(undefined, {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
          })
        : "Unknown Date";
      if (!groups[dateKey]) groups[dateKey] = [];
      groups[dateKey].push(event);
    }
    return groups;
  }

  const grouped = groupByDate(events);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">Calendar</h1>
          <p className="text-sm text-text-muted mt-1">
            Upcoming events from Google Calendar
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-xl border border-border px-4 py-2 text-sm bg-surface-raised text-text-primary focus:border-accent-400 outline-none transition-colors"
          >
            <option value={1}>Today</option>
            <option value={3}>Next 3 days</option>
            <option value={7}>Next 7 days</option>
            <option value={14}>Next 2 weeks</option>
            <option value={30}>Next month</option>
          </select>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 rounded-xl gradient-bg px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
          >
            <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
            {syncing ? "Syncing..." : "Generate Briefings"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <AlertCircle size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-amber-800">
              Calendar unavailable
            </p>
            <p className="text-sm text-amber-700 mt-1">{error}</p>
            <p className="text-xs text-amber-600 mt-2">
              Make sure Google Calendar MCP is connected in{" "}
              <Link
                href="/settings/connections"
                className="underline font-medium"
              >
                Settings
              </Link>
              .
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 rounded-2xl shimmer" />
          ))}
        </div>
      ) : events.length === 0 && !error ? (
        <div className="text-center py-16">
          <CalendarIcon size={48} className="mx-auto mb-4 text-text-muted" />
          <p className="text-lg font-semibold text-text-primary">No upcoming events</p>
          <p className="text-sm mt-1 text-text-muted">
            No events found in the next {days} day{days > 1 ? "s" : ""}.
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([dateLabel, dateEvents]) => (
            <div key={dateLabel}>
              <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-3">
                {dateLabel}
              </h2>
              <div className="space-y-3">
                {dateEvents.map((event) => (
                  <EventCard key={event.event_id} event={event} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EventCard({ event }: { event: CalendarEvent }) {
  function formatTime(iso: string) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  }

  function duration(start: string, end: string) {
    if (!start || !end) return "";
    try {
      const mins = Math.round(
        (new Date(end).getTime() - new Date(start).getTime()) / 60000
      );
      if (mins < 60) return `${mins}m`;
      const hrs = Math.floor(mins / 60);
      const rem = mins % 60;
      return rem ? `${hrs}h ${rem}m` : `${hrs}h`;
    } catch {
      return "";
    }
  }

  return (
    <div className="glass-card p-5">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-text-primary truncate">{event.title}</h3>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-sm text-text-muted">
            <span className="flex items-center gap-1">
              <Clock size={14} />
              {formatTime(event.start)} – {formatTime(event.end)}
              <span className="text-text-muted/60 ml-1">
                ({duration(event.start, event.end)})
              </span>
            </span>
            {event.location && (
              <span className="flex items-center gap-1">
                <MapPin size={14} />
                {event.location}
              </span>
            )}
            {event.attendees.length > 0 && (
              <span className="flex items-center gap-1">
                <Users size={14} />
                {event.attendees.length} attendee
                {event.attendees.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          {event.attendees.length > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {event.attendees.slice(0, 5).map((att, i) => (
                <span
                  key={i}
                  className="badge badge-info"
                >
                  {att.name || att.email || "Unknown"}
                </span>
              ))}
              {event.attendees.length > 5 && (
                <span className="badge badge-neutral">
                  +{event.attendees.length - 5} more
                </span>
              )}
            </div>
          )}

          {event.description && (
            <p className="text-sm text-text-secondary mt-2 line-clamp-2">
              {event.description}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          {event.briefing && (
            <Link
              href={`/briefings/${event.briefing.id}`}
              className="flex items-center gap-1 rounded-xl bg-accent-50 px-3 py-2 text-xs font-semibold text-accent-700 hover:bg-accent-100 transition-colors"
            >
              <FileText size={12} />
              View Briefing
            </Link>
          )}
          {event.html_link && (
            <a
              href={event.html_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-xl border border-border px-3 py-2 text-xs text-text-secondary hover:bg-surface-overlay transition-colors"
            >
              <ExternalLink size={12} />
              Open
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
