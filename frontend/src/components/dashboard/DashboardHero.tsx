"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { format, parseISO, differenceInMinutes, isPast } from "date-fns";
import {
  Clock,
  Calendar,
  Users,
  MapPin,
  Timer,
  ArrowRight,
  ExternalLink,
  CalendarOff,
} from "lucide-react";
import type { CalendarEvent } from "@/lib/types";

function LiveClock() {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col items-start">
      <span className="text-5xl font-bold tracking-tight tabular-nums text-white">
        {format(now, "h:mm")}
        <span className="text-2xl font-medium text-white/60 ml-1">
          {format(now, "ss")}
        </span>
        <span className="text-lg font-medium text-white/50 ml-2 uppercase">
          {format(now, "a")}
        </span>
      </span>
      <span className="text-sm text-white/50 mt-1 font-medium">
        {format(now, "EEEE, MMMM d, yyyy")}
      </span>
    </div>
  );
}

function NextMeetingCard({ event }: { event: CalendarEvent }) {
  const start = parseISO(event.start);
  const end = parseISO(event.end);
  const durationMin = differenceInMinutes(end, start);
  const minutesUntil = differenceInMinutes(start, new Date());
  const isNow = isPast(start) && !isPast(end);

  const urgencyLabel = isNow
    ? "Happening now"
    : minutesUntil <= 0
      ? "Starting now"
      : minutesUntil < 60
        ? `In ${minutesUntil} min`
        : minutesUntil < 1440
          ? `In ${Math.floor(minutesUntil / 60)}h ${minutesUntil % 60}m`
          : `Tomorrow`;

  return (
    <Link
      href={`/calendar/${event.event_id}`}
      className="block rounded-2xl bg-white/10 backdrop-blur-sm border border-white/10 p-5 hover:bg-white/15 transition-all group"
    >
      <div className="flex items-center gap-2 mb-3">
        <div
          className={`rounded-lg px-2.5 py-1 text-xs font-bold ${
            isNow || minutesUntil <= 5
              ? "bg-emerald-400/20 text-emerald-300"
              : minutesUntil <= 30
                ? "bg-amber-400/20 text-amber-300"
                : "bg-white/10 text-white/70"
          }`}
        >
          {urgencyLabel}
        </div>
        <span className="text-[11px] text-white/40 font-medium uppercase tracking-wider">
          Next Meeting
        </span>
      </div>

      <h3 className="text-lg font-semibold text-white truncate group-hover:text-accent-200 transition-colors">
        {event.title}
      </h3>

      <div className="mt-3 flex items-center gap-4 text-xs text-white/50 flex-wrap">
        <span className="flex items-center gap-1.5">
          <Clock size={12} className="text-accent-300" />
          {format(start, "h:mm a")} – {format(end, "h:mm a")}
        </span>
        {durationMin > 0 && (
          <span className="flex items-center gap-1.5">
            <Timer size={12} className="text-cyan-300" />
            {durationMin} min
          </span>
        )}
        {event.attendees.length > 0 && (
          <span className="flex items-center gap-1.5">
            <Users size={12} className="text-violet-300" />
            {event.attendees.length} attendee{event.attendees.length !== 1 && "s"}
          </span>
        )}
        {event.location && (
          <span className="flex items-center gap-1.5 truncate max-w-[200px]">
            <MapPin size={12} className="text-rose-300 shrink-0" />
            {event.location}
          </span>
        )}
      </div>

      {event.attendees.length > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <div className="flex -space-x-1.5">
            {event.attendees.slice(0, 5).map((a, i) => (
              <div
                key={a.email ?? i}
                className="flex h-6 w-6 items-center justify-center rounded-full border border-white/20 text-[9px] font-bold text-white"
                style={{
                  background: [
                    "rgba(99,102,241,0.6)",
                    "rgba(139,92,246,0.6)",
                    "rgba(6,182,212,0.6)",
                    "rgba(245,158,11,0.6)",
                    "rgba(236,72,153,0.6)",
                  ][i % 5],
                }}
                title={a.name || a.email || ""}
              >
                {(a.name || a.email || "?").charAt(0).toUpperCase()}
              </div>
            ))}
            {event.attendees.length > 5 && (
              <div className="flex h-6 w-6 items-center justify-center rounded-full border border-white/20 bg-white/10 text-[9px] font-bold text-white/60">
                +{event.attendees.length - 5}
              </div>
            )}
          </div>
          <span className="text-[11px] text-white/30">
            {event.attendees
              .slice(0, 3)
              .map((a) => (a.name || a.email || "").split(" ")[0])
              .join(", ")}
            {event.attendees.length > 3 && "…"}
          </span>
        </div>
      )}

      <div className="mt-3 flex items-center gap-3">
        {event.html_link && (
          <a
            href={event.html_link}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-[11px] text-white/40 hover:text-white/70 transition-colors"
          >
            <ExternalLink size={10} /> Google Calendar
          </a>
        )}
        <span className="ml-auto flex items-center gap-1 text-[11px] text-accent-300 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
          View details <ArrowRight size={10} />
        </span>
      </div>
    </Link>
  );
}

export function DashboardHero() {
  const { data } = useQuery({
    queryKey: ["calendar-events", 2],
    queryFn: () => api.calendar.events(2),
    retry: false,
  });

  const now = new Date();
  const nextEvent = data?.events?.find((e) => !isPast(parseISO(e.end)));

  return (
    <div className="relative overflow-hidden rounded-3xl mb-8">
      <div className="absolute inset-0 bg-gradient-to-br from-[#1e1b4b] via-[#312e81] to-[#4338ca]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(139,92,246,0.3),transparent_60%)]" />
      <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-accent-500/10 blur-3xl" />
      <div className="absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-cyan-500/10 blur-3xl" />

      <div className="relative z-10 p-8">
        <div className="grid gap-8 lg:grid-cols-2 items-start">
          {/* Left: Clock + greeting */}
          <div>
            <p className="text-sm text-white/40 font-medium mb-4 uppercase tracking-wider flex items-center gap-2">
              <Calendar size={14} className="text-accent-300" />
              Today&apos;s Overview
            </p>
            <LiveClock />
            <p className="mt-4 text-sm text-white/40">
              {nextEvent
                ? "Your next meeting is coming up."
                : "No upcoming meetings. You're free!"}
            </p>
          </div>

          {/* Right: Next meeting */}
          <div>
            {nextEvent ? (
              <NextMeetingCard event={nextEvent} />
            ) : (
              <div className="rounded-2xl bg-white/5 border border-white/10 p-6 text-center">
                <CalendarOff size={28} className="mx-auto text-white/20 mb-3" />
                <p className="text-sm font-medium text-white/50">
                  No upcoming meetings
                </p>
                <p className="text-xs text-white/30 mt-1">
                  Your calendar is clear for the next 2 days.
                </p>
                <Link
                  href="/calendar"
                  className="mt-3 inline-flex items-center gap-1 text-xs text-accent-300 hover:text-accent-200 font-medium transition-colors"
                >
                  View Calendar <ArrowRight size={10} />
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
