"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Search, Clock, ArrowLeft } from "lucide-react";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

function SearchResults() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialQuery = searchParams.get("q") || "";
  const [query, setQuery] = useState(initialQuery);

  const { data, isLoading, error } = useQuery({
    queryKey: ["search", initialQuery],
    queryFn: () => api.search.query({ query: initialQuery }),
    enabled: !!initialQuery,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <Link
        href="/"
        className="flex items-center gap-1.5 text-sm text-accent-500 hover:text-accent-700 font-medium mb-6"
      >
        <ArrowLeft size={14} /> Back to Dashboard
      </Link>

      <h1 className="text-3xl font-bold tracking-tight text-text-primary mb-6">
        Search
      </h1>

      <form onSubmit={handleSearch} className="mb-8">
        <div className="relative glass-card !p-0 overflow-hidden">
          <Search
            size={18}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-accent-400"
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search meetings, people, topics..."
            className="w-full bg-transparent py-4 pl-12 pr-4 text-sm text-text-primary outline-none placeholder:text-text-muted border-none focus:shadow-none"
          />
        </div>
      </form>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 rounded-2xl shimmer" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Search failed: {(error as Error).message}
        </div>
      )}

      {data && (
        <>
          <p className="text-sm text-text-muted mb-4">
            {data.total} result{data.total !== 1 ? "s" : ""} for &ldquo;
            {initialQuery}&rdquo;
          </p>

          <div className="space-y-3">
            {data.results.map((result) => (
              <Link
                key={result.meeting_id}
                href={`/meetings/${result.meeting_id}`}
                className="block glass-card card-accent p-5 pl-6"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-text-primary">
                      {result.title}
                    </h3>
                    <p className="mt-1.5 text-sm text-text-secondary line-clamp-2">
                      {result.snippet}
                    </p>
                    <div className="mt-2.5 flex items-center gap-3 text-xs text-text-muted">
                      {result.date && (
                        <span className="flex items-center gap-1">
                          <Clock size={11} className="text-accent-400" />
                          {(() => {
                            try {
                              return formatDistanceToNow(new Date(result.date), {
                                addSuffix: true,
                              });
                            } catch {
                              return result.date;
                            }
                          })()}
                        </span>
                      )}
                      <span
                        className={`badge ${
                          result.source === "fulltext"
                            ? "badge-info"
                            : result.source === "semantic"
                              ? "badge-violet"
                              : "badge-success"
                        }`}
                      >
                        {result.source}
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {data.total === 0 && (
            <div className="empty-state">
              <div className="icon-box icon-box-lg icon-box-indigo mx-auto">
                <Search size={22} />
              </div>
              <p className="mt-4 text-sm font-medium text-text-secondary">
                No results found
              </p>
              <p className="mt-1 text-xs text-text-muted">
                Try different keywords for &ldquo;{initialQuery}&rdquo;
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 max-w-4xl mx-auto">
          <div className="h-12 rounded-2xl shimmer mb-8" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-2xl shimmer" />
            ))}
          </div>
        </div>
      }
    >
      <SearchResults />
    </Suspense>
  );
}
