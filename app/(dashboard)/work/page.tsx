"use client";

import { useEffect, useState } from "react";
import { checkAuth, fetchEmails, triggerFetch, getLoginUrl, Email } from "@/lib/api";

export default function WorkPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkAuthentication();
  }, []);

  async function checkAuthentication() {
    try {
      setLoading(true);
      setError(null);
      const authResult = await checkAuth();
      setIsAuthenticated(authResult.authenticated);

      if (authResult.authenticated) {
        await loadEmails();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check authentication");
    } finally {
      setLoading(false);
    }
  }

  async function loadEmails() {
    try {
      setError(null);
      const result = await fetchEmails(50, 0);
      setEmails(result.emails);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load emails");
    }
  }

  async function handleFetchNewEmails() {
    try {
      setFetching(true);
      setError(null);
      await triggerFetch();
      await loadEmails();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch new emails");
    } finally {
      setFetching(false);
    }
  }

  function formatDate(dateString: string) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) {
      const diffMins = Math.floor(diffMs / (1000 * 60));
      return `${diffMins}m ago`;
    } else if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else if (diffDays === 1) {
      return "Yesterday";
    } else if (diffDays < 7) {
      return `${diffDays}d ago`;
    } else {
      return date.toLocaleDateString();
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (isAuthenticated === false) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-[#1a1a3a] bg-[#0a0a1e] p-12 text-center">
          <h2 className="mb-4 text-xl font-semibold text-gray-200">
            Connect Your Outlook Account
          </h2>
          <p className="mb-6 text-gray-400">
            To start triaging your emails, please connect your Microsoft Outlook account.
          </p>
          <a
            href={getLoginUrl()}
            className="inline-block rounded-md bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
          >
            Connect Outlook
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header Section */}
      <div className="rounded-lg border border-[#1a1a3a] bg-[#0a0a1e] p-6">
        <div className="flex items-center justify-between">
          <div className="text-lg font-medium text-gray-300">
            {emails.length} emails to process
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleFetchNewEmails}
              disabled={fetching}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {fetching ? "Fetching..." : "Fetch New Emails"}
            </button>
            <button className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-green-700">
              Execute All
            </button>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-lg border border-red-900 bg-red-950 p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Email List */}
      <div className="space-y-3">
        {emails.length === 0 ? (
          <div className="rounded-lg border border-[#1a1a3a] bg-[#0c0c1e] p-12 text-center">
            <p className="text-gray-400">No emails to display</p>
          </div>
        ) : (
          emails.map((email) => (
            <div
              key={email.id}
              className="rounded-lg border border-[#16163a] bg-[#0c0c1e] p-4 transition-colors hover:border-[#20204a] hover:bg-[#0e0e22]"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium text-gray-200 truncate">
                      {email.sender_name || email.sender_email}
                    </h3>
                    {email.importance === "high" && (
                      <span className="inline-flex items-center rounded-full bg-red-900/50 px-2 py-0.5 text-xs font-medium text-red-400">
                        High
                      </span>
                    )}
                    {email.has_attachments && (
                      <span className="inline-flex items-center rounded-full bg-blue-900/50 px-2 py-0.5 text-xs font-medium text-blue-400">
                        📎
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-300 mb-1 truncate">
                    {email.subject}
                  </p>
                  {email.body_preview && (
                    <p className="text-xs text-gray-500 truncate">
                      {email.body_preview}
                    </p>
                  )}
                </div>
                <div className="flex-shrink-0 text-xs text-gray-500">
                  {formatDate(email.received_datetime)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
