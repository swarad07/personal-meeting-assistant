"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileText,
  Clock,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api-client";
import type { Briefing, PaginatedResponse } from "@/lib/types";

export default function BriefingsListPage() {
  const [data, setData] = useState<PaginatedResponse<Briefing> | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    load();
  }, [page]);

  async function load() {
    setLoading(true);
    try {
      const result = await api.briefings.list(page, 10);
      setData(result);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      await api.briefings.generate();
      setTimeout(() => load(), 3000);
    } catch {
      // ignore
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">Briefings</h1>
          <p className="text-sm text-text-muted mt-1">
            AI-generated pre-meeting briefings
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 rounded-xl gradient-bg px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-accent-500/25"
        >
          <RefreshCw size={14} className={generating ? "animate-spin" : ""} />
          {generating ? "Generating..." : "Generate New"}
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-20 rounded-2xl shimmer" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="empty-state">
          <div className="icon-box icon-box-lg icon-box-violet mx-auto">
            <FileText size={22} />
          </div>
          <p className="mt-4 text-sm font-medium text-text-secondary">No briefings yet</p>
          <p className="text-xs mt-1 text-text-muted">
            Briefings are generated automatically before your upcoming meetings,
            or you can generate them manually.
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {data.items.map((briefing) => (
              <Link
                key={briefing.id}
                href={`/briefings/${briefing.id}`}
                className="block glass-card card-accent p-5 pl-6"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-text-primary truncate">
                      {briefing.title}
                    </h3>
                    <p className="text-sm text-text-secondary mt-1.5 line-clamp-2">
                      {briefing.content.slice(0, 200)}
                      {briefing.content.length > 200 ? "..." : ""}
                    </p>
                    <div className="flex items-center gap-3 mt-2.5 text-xs text-text-muted">
                      {briefing.created_at && (
                        <span className="flex items-center gap-1">
                          <Clock size={12} className="text-accent-400" />
                          {new Date(briefing.created_at).toLocaleString(
                            undefined,
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            }
                          )}
                        </span>
                      )}
                      {briefing.topics && Array.isArray(briefing.topics) && (
                        <span className="badge badge-violet">
                          {briefing.topics.length} discussion point
                          {briefing.topics.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="icon-box icon-box-md icon-box-violet ml-4">
                    <FileText size={18} />
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {data.total_pages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <p className="text-sm text-text-muted">
                Page {data.page} of {data.total_pages} ({data.total} briefings)
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="flex items-center gap-1 rounded-xl border border-border px-4 py-2 text-sm font-medium text-text-secondary disabled:opacity-50 hover:bg-surface-overlay transition-colors"
                >
                  <ChevronLeft size={14} />
                  Previous
                </button>
                <button
                  onClick={() =>
                    setPage((p) => Math.min(data.total_pages, p + 1))
                  }
                  disabled={page >= data.total_pages}
                  className="flex items-center gap-1 rounded-xl border border-border px-4 py-2 text-sm font-medium text-text-secondary disabled:opacity-50 hover:bg-surface-overlay transition-colors"
                >
                  Next
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
