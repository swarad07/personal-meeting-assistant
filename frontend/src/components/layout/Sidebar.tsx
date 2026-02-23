"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  GitBranch,
  Users,
  Calendar,
  FileText,
  CheckSquare,
  Bot,
  Settings,
  Search,
  ChevronLeft,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/meetings", label: "Meetings", icon: MessageSquare },
  { href: "/search", label: "Search", icon: Search },
  { href: "/relationships", label: "Relationships", icon: GitBranch },
  { href: "/profiles/me", label: "Profiles", icon: Users },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/briefings", label: "Briefings", icon: FileText },
  { href: "/action-items", label: "Action Items", icon: CheckSquare },
  { href: "/agents", label: "Agents", icon: Bot },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery("");
    }
  }

  return (
    <aside
      className={cn(
        "flex flex-col sidebar-gradient transition-all duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-white/10 px-4">
        {!collapsed && (
          <div className="flex items-center gap-2 truncate">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/15">
              <Sparkles size={14} className="text-accent-300" />
            </div>
            <span className="text-sm font-semibold text-white tracking-tight truncate">
              Meeting AI
            </span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-md text-white/50 hover:bg-white/10 hover:text-white transition-colors",
            collapsed && "mx-auto",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronLeft
            size={16}
            className={cn(
              "transition-transform duration-200",
              collapsed && "rotate-180",
            )}
          />
        </button>
      </div>

      {/* Search */}
      {!collapsed ? (
        <div className="px-3 pt-3 pb-1">
          <form onSubmit={handleSearch}>
            <div className="relative">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/40"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
                className="w-full rounded-lg border border-white/10 bg-white/8 py-1.5 pl-8 pr-8 text-xs text-white outline-none focus:border-accent-400 focus:bg-white/12 placeholder:text-white/30 transition-all"
              />
              <kbd className="absolute right-2 top-1/2 -translate-y-1/2 hidden sm:inline-flex items-center rounded border border-white/15 bg-white/5 px-1 text-[10px] text-white/30 font-mono">
                &#8984;K
              </kbd>
            </div>
          </form>
        </div>
      ) : (
        <div className="px-2 pt-3 pb-1">
          <button
            onClick={() => {
              setCollapsed(false);
              setTimeout(() => {
                const input = document.querySelector<HTMLInputElement>(
                  "aside input[type='text']"
                );
                input?.focus();
              }, 250);
            }}
            className="flex h-8 w-full items-center justify-center rounded-lg text-white/40 hover:bg-white/10 hover:text-white/80"
            title="Search"
          >
            <Search size={16} />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
              isActive(href)
                ? "bg-white/15 text-white shadow-sm"
                : "text-white/60 hover:bg-white/8 hover:text-white/90",
              collapsed && "justify-center px-0",
            )}
            title={collapsed ? label : undefined}
          >
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </Link>
        ))}
      </nav>

      {/* Settings (bottom) */}
      <div className="border-t border-white/10 px-2 py-3">
        <Link
          href="/settings/connections"
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150",
            isActive("/settings")
              ? "bg-white/15 text-white shadow-sm"
              : "text-white/60 hover:bg-white/8 hover:text-white/90",
            collapsed && "justify-center px-0",
          )}
          title={collapsed ? "Settings" : undefined}
        >
          <Settings size={18} className="shrink-0" />
          {!collapsed && <span className="truncate">Settings</span>}
        </Link>
      </div>
    </aside>
  );
}
