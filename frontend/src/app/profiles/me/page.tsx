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
import { User, MessageSquare, Save, Users, Loader2, Search, X, AlertCircle, Mail } from "lucide-react";
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

  const [contactSearch, setContactSearch] = useState("");
  const [editing, setEditing] = useState(false);

  const allContacts = useMemo(
    () =>
      (contactsPages?.pages.flatMap((p) => p.items) ?? []).filter(
        (p) => p.type !== "self",
      ),
    [contactsPages],
  );
  const totalContacts = contactsPages?.pages[0]?.total ?? 0;

  const contacts = useMemo(() => {
    if (!contactSearch.trim()) return allContacts;
    const q = contactSearch.toLowerCase();
    return allContacts.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.email && c.email.toLowerCase().includes(q)) ||
        (c.bio && c.bio.toLowerCase().includes(q)),
    );
  }, [allContacts, contactSearch]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [bio, setBio] = useState("");
  const [notes, setNotes] = useState("");

  const updateMutation = useMutation({
    mutationFn: (data: { name?: string; email?: string; bio?: string; notes?: string }) =>
      api.profiles.update("me", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", "me"] });
      setEditing(false);
    },
  });

  const startEditing = () => {
    if (profile) {
      setName(profile.name);
      setEmail(profile.email || "");
      setBio(profile.bio || "");
      setNotes(profile.notes || "");
      setEditing(true);
    }
  };

  const needsSetup = profile && (profile.name === "Me" || !profile.email);

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
                  <div className="space-y-1.5">
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Your full name"
                      className="text-lg font-bold text-text-primary border-b-2 border-accent-300 outline-none focus:border-accent-500 bg-transparent block"
                    />
                    <div className="flex items-center gap-1.5">
                      <Mail size={12} className="text-text-muted" />
                      <input
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="your@email.com"
                        type="email"
                        className="text-sm text-text-secondary border-b border-border outline-none focus:border-accent-400 bg-transparent"
                      />
                    </div>
                  </div>
                ) : (
                  <div>
                    <h2 className="text-lg font-bold text-text-primary">
                      {profile.name}
                    </h2>
                    {profile.email && (
                      <p className="text-xs text-text-muted flex items-center gap-1">
                        <Mail size={10} />
                        {profile.email}
                      </p>
                    )}
                  </div>
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
                  onClick={() => updateMutation.mutate({ name, email, bio, notes })}
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

      {needsSetup && !editing && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50/50 p-5 flex items-start gap-3">
          <AlertCircle size={20} className="text-amber-500 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-amber-800">
              Set up your identity
            </h3>
            <p className="text-xs text-amber-700 mt-0.5">
              Your identity is set automatically when you connect Granola.
              If it wasn&apos;t detected, enter your name and email below so the
              tool can recognize you in meetings and action items.
            </p>
          </div>
          <button
            onClick={startEditing}
            className="shrink-0 rounded-xl bg-amber-500 px-4 py-2 text-xs font-semibold text-white hover:bg-amber-600 transition-colors"
          >
            Set up now
          </button>
        </div>
      )}

      <section>
        <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Users size={18} className="text-accent-400" />
            <h2 className="text-lg font-bold text-text-primary">
              Contacts
            </h2>
            <span className="text-sm text-text-muted">
              ({contactSearch ? `${contacts.length} of ${totalContacts}` : totalContacts})
            </span>
          </div>
          <div className="relative w-full max-w-xs">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
            />
            <input
              type="text"
              value={contactSearch}
              onChange={(e) => setContactSearch(e.target.value)}
              placeholder="Search contacts..."
              className="w-full rounded-xl border border-border bg-surface py-2 pl-9 pr-8 text-xs text-text-primary outline-none focus:border-accent-400 focus:shadow-[0_0_0_3px_rgba(99,102,241,0.1)] placeholder:text-text-muted transition-all"
            />
            {contactSearch && (
              <button
                onClick={() => setContactSearch("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        {contactSearch && contacts.length === 0 && (
          <p className="text-sm text-text-muted text-center py-8">
            No contacts matching &quot;{contactSearch}&quot;
          </p>
        )}

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
