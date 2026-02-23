"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

export default function OAuthCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );
  const [message, setMessage] = useState("Processing authentication...");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      setStatus("error");
      setMessage(
        searchParams.get("error_description") ||
          `Authorization failed: ${error}`
      );
      return;
    }

    if (!code) {
      setStatus("error");
      setMessage("No authorization code received.");
      return;
    }

    const provider = state || "granola";

    (async () => {
      try {
        const result = await api.connections.callback(
          provider,
          code,
          window.location.origin + "/settings/connections/callback"
        );
        if (result.connected) {
          setStatus("success");
          setMessage(`${provider} connected successfully!`);
          setTimeout(() => router.push("/settings/connections"), 2000);
        } else {
          setStatus("error");
          setMessage(`Failed to connect ${provider}. Please try again.`);
        }
      } catch (err) {
        setStatus("error");
        setMessage(
          err instanceof Error ? err.message : "Token exchange failed."
        );
      }
    })();
  }, [searchParams, router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-8">
      <div className="glass-card w-full max-w-md p-8 text-center">
        {status === "loading" && (
          <>
            <Loader2
              size={48}
              className="mx-auto mb-4 animate-spin text-accent-500"
            />
            <h2 className="text-lg font-semibold text-text-primary">
              Connecting...
            </h2>
            <p className="mt-2 text-sm text-text-secondary">{message}</p>
          </>
        )}

        {status === "success" && (
          <>
            <CheckCircle size={48} className="mx-auto mb-4 text-emerald-500" />
            <h2 className="text-lg font-semibold text-text-primary">
              Connected!
            </h2>
            <p className="mt-2 text-sm text-text-secondary">{message}</p>
            <p className="mt-4 text-xs text-text-muted">
              Redirecting to connections...
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <XCircle size={48} className="mx-auto mb-4 text-red-500" />
            <h2 className="text-lg font-semibold text-text-primary">
              Connection Failed
            </h2>
            <p className="mt-2 text-sm text-text-secondary">{message}</p>
            <button
              onClick={() => router.push("/settings/connections")}
              className="mt-6 rounded-xl gradient-bg px-6 py-2 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-lg shadow-accent-500/25"
            >
              Back to Connections
            </button>
          </>
        )}
      </div>
    </div>
  );
}
