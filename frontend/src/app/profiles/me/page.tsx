"use client";

import Link from "next/link";
import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { User, MessageSquare, Save, Users, Loader2 } from "lucide-react";
import { getInitials } from "@/lib/utils";

const CONTACTS_PAGE_SIZE = 30;

export default function MyProfilePage() {
  const queryClient = useQueryClient();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile", "me"],
    queryFn: () => api.profiles.me(),
  });

  const {
    data: contactsPages,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["profiles", "contacts-infinite"],
    queryFn: ({ pageParam = 1 }) =>
      api.profiles.list(pageParam, CONTACTS_PAGE_SIZE),
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

  const contacts = useMemo(
    () =>
      (contactsPages?.pages.flatMap((p) => p.items) ?? []).filter(
        (p) => p.type !== "self",
      ),
    [contactsPages],
  );
  const totalContacts = contactsPages?.pages[0]?.total ?? 0;

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [notes, setNotes] = useState("");

  const updateMutation = useMutation({
    mutationFn: (data: { name?: string; bio?: string; notes?: string }) =>
      api.profiles.update("me", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", "me"] });
      setEditing(false);
    },
  });

  const startEditing = () => {
    if (profile) {
      setName(profile.name);
      setBio(profile.bio || "");
      setNotes(profile.notes || "");
      setEditing(true);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <div className="h-48 rounded-2xl shimmer mb-6" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">Profiles</h1>
      </div>

      {profile && (
        <section className="glass-card p-6 mb-8">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-14 w-14 items-center justify-center rounded-full gradient-bg text-white">
                <User size={24} />
              </div>
              <div>
                {editing ? (
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="text-lg font-bold text-text-primary border-b-2 border-accent-300 outline-none focus:border-accent-500 bg-transparent"
                  />
                ) : (
                  <h2 className="text-lg font-bold text-text-primary">
                    {profile.name}
                  </h2>
                )}
                <p className="text-xs text-text-muted">Your personal profile</p>
              </div>
            </div>
            {editing ? (
              <div className="flex gap-2">
                <button
                  onClick={() => setEditing(false)}
                  className="rounded-xl border border-border px-4 py-2 text-sm text-text-secondary hover:bg-surface-overlay transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => updateMutation.mutate({ name, bio, notes })}
                  disabled={updateMutation.isPending}
                  className="flex items-center gap-1.5 rounded-xl gradient-bg px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
                >
                  <Save size={13} /> Save
                </button>
              </div>
            ) : (
              <button
                onClick={startEditing}
                className="rounded-xl border border-border px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-overlay transition-colors"
              >
                Edit
              </button>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-text-muted mb-1 block uppercase tracking-wide">Bio</label>
              {editing ? (
                <textarea
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  rows={3}
                  className="w-full rounded-xl border border-border px-4 py-3 text-sm text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.1)] transition-all"
                />
              ) : (
                <p className="text-sm text-text-secondary">{profile.bio || "No bio set"}</p>
              )}
            </div>
            <div>
              <label className="text-xs font-semibold text-text-muted mb-1 block uppercase tracking-wide">Notes</label>
              {editing ? (
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  className="w-full rounded-xl border border-border px-4 py-3 text-sm text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.1)] transition-all"
                />
              ) : (
                <p className="text-sm text-text-secondary">
                  {profile.notes || "Add personal notes here"}
                </p>
              )}
            </div>
          </div>
        </section>
      )}

      <section>
        <div className="flex items-center gap-2 mb-4">
          <Users size={18} className="text-accent-400" />
          <h2 className="text-lg font-bold text-text-primary">
            Contacts
          </h2>
          <span className="text-sm text-text-muted">({totalContacts})</span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {contacts.map((contact, i) => (
            <Link
              key={contact.id}
              href={`/profiles/${contact.id}`}
              className="glass-card p-4"
            >
              <div className="flex items-start gap-3">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
                  style={{
                    background: [
                      "linear-gradient(135deg, #6366f1, #818cf8)",
                      "linear-gradient(135deg, #8b5cf6, #a78bfa)",
                      "linear-gradient(135deg, #06b6d4, #22d3ee)",
                      "linear-gradient(135deg, #f59e0b, #fbbf24)",
                    ][i % 4],
                  }}
                >
                  {getInitials(contact.name)}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text-primary truncate">
                    {contact.name}
                  </p>
                  {contact.bio && (
                    <p className="text-xs text-text-muted truncate">{contact.bio}</p>
                  )}
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-text-muted">
                    <span className="flex items-center gap-0.5">
                      <MessageSquare size={10} />
                      {contact.meeting_count} meetings
                    </span>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="h-1" />
        {isFetchingNextPage && (
          <div className="flex justify-center py-6">
            <Loader2 size={20} className="animate-spin text-accent-400" />
          </div>
        )}
        {!hasNextPage && contacts.length > 0 && (
          <p className="text-center text-xs text-text-muted py-4">
            All contacts loaded
          </p>
        )}
      </section>
    </div>
  );
}
