"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import Link from "next/link";
import { CheckSquare, Clock, User } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { getInitials } from "@/lib/utils";
import type { Profile } from "@/lib/types";

const STATUS_TABS = [
  { value: undefined, label: "All" },
  { value: "open", label: "Open" },
  { value: "done", label: "Done" },
  { value: "dismissed", label: "Dismissed" },
] as const;

const AVATAR_GRADIENTS = [
  "linear-gradient(135deg, #6366f1, #818cf8)",
  "linear-gradient(135deg, #8b5cf6, #a78bfa)",
  "linear-gradient(135deg, #06b6d4, #22d3ee)",
  "linear-gradient(135deg, #f59e0b, #fbbf24)",
  "linear-gradient(135deg, #ec4899, #f472b6)",
  "linear-gradient(135deg, #10b981, #34d399)",
];

function getGradient(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length];
}


export default function ActionItemsPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>("open");
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["actionItems", statusFilter],
    queryFn: () => api.actionItems.list(statusFilter),
  });

  const { data: profilesData } = useQuery({
    queryKey: ["profiles-for-action-items"],
    queryFn: () => api.profiles.list(1, 500),
  });

  const profilesByName = new Map<string, Profile>();
  if (profilesData?.items) {
    for (const p of profilesData.items) {
      profilesByName.set(p.name.toLowerCase(), p);
    }
  }

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.actionItems.update(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actionItems"] });
    },
  });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">
            Action Items
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {data ? `${data.total} total` : "Loading..."}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1 rounded-2xl bg-surface-overlay p-1 mb-6 w-fit">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.label}
            onClick={() => setStatusFilter(tab.value)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition-all ${
              statusFilter === tab.value
                ? "bg-white text-text-primary shadow-sm"
                : "text-text-muted hover:text-text-secondary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 rounded-2xl shimmer" />
          ))}
        </div>
      )}

      {data && (
        <div className="space-y-2">
          {data.items.map((item) => {
            const assignee = item.assignee || "Unassigned";
            const profile = profilesByName.get(assignee.toLowerCase());

            return (
              <div key={item.id} className="flex items-start gap-3 glass-card p-4">
                <button
                  onClick={() =>
                    updateMutation.mutate({
                      id: item.id,
                      status: item.status === "done" ? "open" : "done",
                    })
                  }
                  className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all ${
                    item.status === "done"
                      ? "border-emerald-500 bg-emerald-500 text-white"
                      : "border-accent-300 hover:border-accent-400"
                  }`}
                >
                  {item.status === "done" && <CheckSquare size={12} />}
                </button>

                <div className="min-w-0 flex-1">
                  <p
                    className={`text-sm leading-relaxed ${
                      item.status === "done"
                        ? "text-text-muted line-through"
                        : "text-text-primary"
                    }`}
                  >
                    {item.description}
                  </p>

                  <div className="mt-2 flex items-center gap-3 flex-wrap">
                    {/* Assignee chip */}
                    {profile ? (
                      <Link
                        href={`/profiles/${profile.id}`}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-accent-50/60 hover:bg-accent-100/60 pl-1 pr-2.5 py-1 transition-colors"
                      >
                        <div
                          className="flex h-5 w-5 items-center justify-center rounded-full text-[8px] font-bold text-white"
                          style={{ background: getGradient(assignee) }}
                        >
                          {getInitials(assignee)}
                        </div>
                        <span className="text-xs font-semibold text-accent-700">
                          {assignee}
                        </span>
                      </Link>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-secondary/60 pl-1 pr-2.5 py-1">
                        <div
                          className="flex h-5 w-5 items-center justify-center rounded-full text-[8px] font-bold text-white"
                          style={{ background: getGradient(assignee) }}
                        >
                          {getInitials(assignee)}
                        </div>
                        <span className="text-xs font-semibold text-text-secondary">
                          {assignee}
                        </span>
                      </span>
                    )}

                    <Link
                      href={`/meetings/${item.meeting_id}`}
                      className="text-xs text-text-muted hover:text-accent-500 underline transition-colors"
                    >
                      View meeting
                    </Link>

                    <span className="flex items-center gap-0.5 text-xs text-text-muted">
                      <Clock size={10} />
                      {formatDistanceToNow(new Date(item.created_at), {
                        addSuffix: true,
                      })}
                    </span>
                  </div>
                </div>

                {item.status === "open" && (
                  <button
                    onClick={() =>
                      updateMutation.mutate({
                        id: item.id,
                        status: "dismissed",
                      })
                    }
                    className="text-xs text-text-muted hover:text-red-500 transition-colors font-medium mt-1"
                  >
                    Dismiss
                  </button>
                )}
              </div>
            );
          })}

          {data.items.length === 0 && (
            <div className="rounded-2xl border-2 border-dashed border-border p-12 text-center">
              <CheckSquare className="mx-auto h-10 w-10 text-text-muted" />
              <p className="mt-3 text-sm text-text-muted">
                No {statusFilter || ""} action items
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
