"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Search, MessageSquare, Users, GitBranch, CheckSquare, Bot } from "lucide-react";

const NAV_ITEMS = [
  { label: "Meetings", href: "/meetings", icon: MessageSquare },
  { label: "Relationships", href: "/relationships", icon: GitBranch },
  { label: "Profiles", href: "/profiles/me", icon: Users },
  { label: "Action Items", href: "/action-items", icon: CheckSquare },
  { label: "Agents", href: "/agents", icon: Bot },
];

export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleSearch = useCallback(() => {
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      setOpen(false);
      setQuery("");
    }
  }, [query, router]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={() => setOpen(false)}
      />

      <div className="absolute left-1/2 top-[20%] w-full max-w-lg -translate-x-1/2">
        <Command className="rounded-2xl border border-border bg-surface-raised shadow-2xl overflow-hidden">
          <Command.Input
            placeholder="Search meetings, people, topics..."
            value={query}
            onValueChange={setQuery}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            className="w-full border-b border-border bg-transparent px-5 py-4 text-sm text-text-primary outline-none placeholder:text-text-muted"
          />
          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="px-4 py-6 text-center text-sm text-text-muted">
              Press Enter to search for &ldquo;{query}&rdquo;
            </Command.Empty>

            {query.trim() && (
              <Command.Group
                heading="Search"
                className="px-2 py-1.5 text-xs font-semibold text-text-muted uppercase tracking-wide"
              >
                <Command.Item
                  className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-text-primary aria-selected:bg-accent-50 aria-selected:text-accent-700 transition-colors"
                  onSelect={handleSearch}
                >
                  <Search size={14} />
                  Search for &ldquo;{query}&rdquo;
                </Command.Item>
              </Command.Group>
            )}

            <Command.Group
              heading="Navigate"
              className="px-2 py-1.5 text-xs font-semibold text-text-muted uppercase tracking-wide"
            >
              {NAV_ITEMS.map(({ label, href, icon: Icon }) => (
                <Command.Item
                  key={href}
                  className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-text-primary aria-selected:bg-accent-50 aria-selected:text-accent-700 transition-colors"
                  onSelect={() => {
                    router.push(href);
                    setOpen(false);
                    setQuery("");
                  }}
                >
                  <Icon size={14} />
                  {label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
