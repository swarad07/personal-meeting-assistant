"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { getInitials } from "@/lib/utils";
import { format } from "date-fns";
import { toast } from "sonner";
import {
  ArrowLeft,
  Mail,
  MessageSquare,
  CheckSquare,
  Clock,
  Briefcase,
  Sparkles,
  Loader2,
} from "lucide-react";

export default function ProfileDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const queryClient = useQueryClient();

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ["profile", id],
    queryFn: () => api.profiles.get(id),
  });

  const bioMutation = useMutation({
    mutationFn: () => api.profiles.generateBio(id),
    onMutate: () => {
      toast.loading("Generating bio...", { id: "generate-bio" });
    },
    onSuccess: (data) => {
      if (data.status === "success") {
        toast.success("Bio generated successfully", { id: "generate-bio" });
      } else if (data.status === "skipped") {
        toast.info(data.reason || "No data available to generate bio", { id: "generate-bio" });
      } else {
        toast.error(data.reason || "Bio generation failed", { id: "generate-bio" });
      }
      queryClient.invalidateQueries({ queryKey: ["profile", id] });
    },
    onError: (err) => {
      toast.error((err as Error).message || "Failed to generate bio", { id: "generate-bio" });
    },
  });

  if (isLoading) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="h-8 w-48 rounded-xl shimmer mb-6" />
        <div className="h-48 rounded-2xl shimmer" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <Link href="/profiles/me" className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6">
          <ArrowLeft size={14} /> Back to Profiles
        </Link>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error ? (error as Error).message : "Profile not found"}
        </div>
      </div>
    );
  }

  const traits = (profile.traits || {}) as Record<string, unknown>;
  const roles = (traits.observed_roles as string[]) || [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link href="/profiles/me" className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6">
        <ArrowLeft size={14} /> Back to Profiles
      </Link>

      <div className="flex items-start justify-between gap-4 mb-8">
        <div className="flex items-start gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full gradient-bg text-lg font-bold text-white shrink-0">
            {getInitials(profile.name)}
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              {profile.name}
            </h1>
            <div className="mt-1 flex items-center gap-3 text-sm text-text-muted">
              {profile.email && (
                <span className="flex items-center gap-1">
                  <Mail size={13} /> {profile.email}
                </span>
              )}
              {roles.length > 0 && (
                <span className="flex items-center gap-1">
                  <Briefcase size={13} /> {roles.join(", ")}
                </span>
              )}
            </div>
            {profile.bio && (
              <p className="mt-2 text-sm text-text-secondary">{profile.bio}</p>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-2 shrink-0">
          {profile.type !== "self" && (
            <button
              onClick={() => bioMutation.mutate()}
              disabled={bioMutation.isPending}
              className="flex items-center gap-1.5 rounded-xl gradient-bg px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
            >
              {bioMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              {profile.bio ? "Regenerate Bio" : "Generate Bio"}
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-3 grid gap-4 sm:grid-cols-3">
          <div className="glass-card p-5">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">Meetings Together</p>
            <p className="text-2xl font-bold text-text-primary mt-1">
              {profile.meeting_count}
            </p>
          </div>
          <div className="glass-card p-5">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">Open Actions</p>
            <p className="text-2xl font-bold text-text-primary mt-1">
              {profile.action_items.length}
            </p>
          </div>
          <div className="glass-card p-5">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">Last Seen</p>
            <p className="text-sm font-semibold text-text-primary mt-1">
              {traits.last_seen
                ? format(new Date(traits.last_seen as string), "MMM d, yyyy")
                : profile.recent_meetings[0]
                  ? format(new Date(profile.recent_meetings[0].date), "MMM d, yyyy")
                  : "—"}
            </p>
          </div>
        </div>

        <section className="lg:col-span-2 glass-card p-6">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-4 uppercase tracking-wide">
            <MessageSquare size={15} className="text-accent-400" /> Recent Meetings
          </h2>
          {profile.recent_meetings.length > 0 ? (
            <ul className="space-y-2">
              {profile.recent_meetings.map((m) => (
                <li key={m.id}>
                  <Link
                    href={`/meetings/${m.id}`}
                    className="block rounded-xl p-3 hover:bg-accent-50/50 transition-colors"
                  >
                    <p className="text-sm font-medium text-text-primary">
                      {m.title}
                    </p>
                    {m.summary && (
                      <p className="text-xs text-text-muted mt-0.5 line-clamp-2">
                        {m.summary}
                      </p>
                    )}
                    <p className="text-xs text-text-muted mt-1 flex items-center gap-1">
                      <Clock size={10} />
                      {format(new Date(m.date), "MMM d, yyyy")}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">No meetings recorded</p>
          )}
        </section>

        <section className="glass-card p-6">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary mb-4 uppercase tracking-wide">
            <CheckSquare size={15} className="text-accent-400" /> Open Actions
          </h2>
          {profile.action_items.length > 0 ? (
            <ul className="space-y-2.5">
              {profile.action_items.map((ai) => (
                <li key={ai.id} className="flex items-start gap-2">
                  <div className="mt-0.5 h-4 w-4 shrink-0 rounded-md border-2 border-accent-300" />
                  <div className="min-w-0">
                    <p className="text-sm text-text-primary">{ai.description}</p>
                    <Link
                      href={`/meetings/${ai.meeting_id}`}
                      className="text-xs text-accent-500 hover:text-accent-700 underline transition-colors"
                    >
                      View meeting
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-text-muted">No open action items</p>
          )}
        </section>

        {profile.notes && (
          <section className="lg:col-span-3 glass-card p-6">
            <h2 className="text-sm font-semibold text-text-primary mb-2 uppercase tracking-wide">Notes</h2>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">
              {profile.notes}
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
