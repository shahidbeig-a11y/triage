"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { EmailRow } from "@/components";
import Toast, { type ToastMessage } from "@/components/Toast";
import type { Email as EmailType, Category, Folder } from "@/components";
import {
  checkAuth,
  fetchEmails,
  getLoginUrl,
  fetchFolders,
  fetchCategories,
  type Email,
  type AuthResponse,
} from "@/lib/api";

export default function UnclassifiedPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [userName, setUserName] = useState<string>("");
  const [emails, setEmails] = useState<Email[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openEmailId, setOpenEmailId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  function showToast(message: string, type: ToastMessage["type"] = "success") {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }

  function dismissToast(id: string) {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }

  useEffect(() => {
    initializePage();
  }, []);

  async function initializePage() {
    try {
      setLoading(true);
      setError(null);

      const authResult = await checkAuth();
      setIsAuthenticated(authResult.authenticated);

      if (authResult.authenticated) {
        setUserName(authResult.name || authResult.email || "User");
        await Promise.all([loadEmails(), loadFolders(), loadCategories()]);
      }
    } catch (err) {
      console.error("Initialization error:", err);
      setIsAuthenticated(false);
      setError(err instanceof Error ? err.message : "Failed to connect to backend");
    } finally {
      setLoading(false);
    }
  }

  async function loadEmails() {
    try {
      const result = await fetchEmails();
      const normalizedEmails = (result.emails || []).map((email: any) => ({
        ...email,
        id: email.id?.toString() || email.message_id,
        category_id: email.category_id?.toString() || null,
        confidence: email.confidence || 0,
        urgency_score: email.urgency_score || 0,
        due_date: email.due_date || null,
        folder: email.folder || null,
        status: email.status || "unprocessed",
        floor_override: email.floor_override || false,
        stale_days: email.stale_days || 0,
        todo_task_id: email.todo_task_id || null,
        assigned_to: email.assigned_to || null,
      }));

      // Filter to actioned emails with no category (unclassified)
      const unclassifiedEmails = normalizedEmails.filter((email) =>
        email.status === "actioned" && !email.category_id
      );
      setEmails(unclassifiedEmails);
    } catch (err) {
      console.error("Email fetch error:", err);
      throw err;
    }
  }

  async function loadFolders() {
    try {
      const folderData = await fetchFolders();
      setFolders(folderData);
    } catch (err) {
      console.error("Failed to load folders:", err);
      setFolders([]);
    }
  }

  async function loadCategories() {
    try {
      const allCats = await fetchCategories();
      setAllCategories(allCats);
    } catch (err) {
      console.error("Failed to load categories:", err);
    }
  }

  async function handleRefresh() {
    try {
      setRefreshing(true);
      setError(null);
      await loadEmails();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh data");
    } finally {
      setRefreshing(false);
    }
  }

  function handleToggle(emailId: string) {
    setOpenEmailId((prev) => (prev === emailId ? null : emailId));
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <RefreshCw className="w-8 h-8 text-[#8888a8] animate-spin mx-auto mb-4" />
            <p className="text-[#8888a8]">Loading unclassified emails...</p>
          </div>
        </div>
      </div>
    );
  }

  if (isAuthenticated === false) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-[#16163a] bg-[#13132d] p-12 text-center">
          <h2 className="mb-4 text-xl font-semibold text-[#E0E0EE]">
            Connect Your Outlook Account
          </h2>
          <p className="mb-6 text-[#8888a8]">
            To start triaging your emails, please connect your Microsoft Outlook account.
          </p>
          <a
            href={getLoginUrl()}
            className="inline-block rounded-md bg-[#3B82F6] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#2563EB]"
          >
            Connect Outlook
          </a>
        </div>
      </div>
    );
  }

  return (
    <>
      <Toast toasts={toasts} onDismiss={dismissToast} />
      <div className="space-y-4">
        <div className="rounded-lg border border-[#16163a] bg-[#13132d] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-[#E0E0EE]">All Mail / Unclassified</h1>
              <span className="px-2.5 py-1 text-sm font-bold bg-[#6B7280] text-white rounded">
                {emails.length}
              </span>
              {userName && <span className="text-sm text-[#8888a8]">· {userName}</span>}
            </div>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#E0E0EE] bg-[#16163a] hover:bg-[#1a1a3a] rounded transition-colors disabled:opacity-50"
            >
              <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-[#D94F4F] bg-[#D94F4F]/10 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-[#D94F4F]">{error}</p>
              <button
                onClick={() => setError(null)}
                className="text-[#D94F4F] hover:text-[#E05555] transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {emails.length === 0 ? (
          <div className="rounded-lg border border-[#16163a] bg-[#13132d] p-16 text-center">
            <div className="text-6xl mb-4">✓</div>
            <h2 className="text-2xl font-semibold text-[#E0E0EE] mb-2">
              No unclassified emails
            </h2>
            <p className="text-[#8888a8]">All emails have been classified.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {emails.map((email) => (
              <EmailRow
                key={email.id}
                email={email as EmailType}
                categories={allCategories}
                folders={folders}
                isOpen={openEmailId === email.id}
                onToggle={() => handleToggle(email.id)}
                onApprove={() => {}}
                onChange={() => {}}
                onCreateFolder={() => {}}
                isApproved={false}
                hasUnsavedChanges={false}
                isFadingOut={false}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
