"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Play, ChevronDown } from "lucide-react";
import { EmailRow } from "@/components";
import Toast, { type ToastMessage } from "@/components/Toast";
import type { Email as EmailType, Category, Folder } from "@/components";
import {
  checkAuth,
  fetchEmails,
  fetchEmailSummary,
  runPipeline,
  getLoginUrl,
  fetchFolders,
  fetchCategories,
  createFolder as apiCreateFolder,
  reclassifyEmail,
  approveEmail,
  unapproveEmail,
  executeApprovedEmails,
  type Email,
  type EmailSummary,
  type AuthResponse,
} from "@/lib/api";

type SortMode = "category" | "due_date";
type DateGroup = "today" | "tomorrow" | "this_week" | "next_week" | "no_date";

export default function WorkPage() {
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [userName, setUserName] = useState<string>("");

  // Data state
  const [emails, setEmails] = useState<Email[]>([]);
  const [summary, setSummary] = useState<EmailSummary | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [workCategories, setWorkCategories] = useState<Category[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("category");

  // Email interaction state
  const [openEmailId, setOpenEmailId] = useState<string | null>(null);
  const [approvedEmails, setApprovedEmails] = useState<Set<string>>(new Set());
  const [pendingChanges, setPendingChanges] = useState<Map<string, Partial<Email>>>(
    new Map()
  );
  const [fadingOutEmails, setFadingOutEmails] = useState<Set<string>>(new Set());

  // Execution state
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionSummary, setExecutionSummary] = useState<{
    executed: number;
    folders_moved: number;
    todos_created: number;
  } | null>(null);

  // Toast notifications
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

      // Check authentication
      const authResult = await checkAuth();
      setIsAuthenticated(authResult.authenticated);

      if (authResult.authenticated) {
        setUserName(authResult.name || authResult.email || "User");
        await Promise.all([loadEmails(), loadSummary(), loadFolders(), loadCategories()]);
      }
    } catch (err) {
      console.error("Initialization error:", err);
      // If auth check fails, treat as not authenticated
      setIsAuthenticated(false);
      setError(
        err instanceof Error ? err.message : "Failed to connect to backend"
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadEmails() {
    try {
      // Fetch all emails for now - the backend might not have category_id set yet
      const result = await fetchEmails();

      console.log("Fetched emails result:", result);
      console.log("Total emails:", result.emails?.length || 0);

      if (result.emails && result.emails.length > 0) {
        console.log("First email sample:", JSON.stringify(result.emails[0], null, 2));
      }

      // Normalize the emails to match our Email interface
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

      // Filter to only Work emails (categories 1-6) that haven't been actioned yet
      const workEmails = normalizedEmails.filter((email) => {
        const catId = parseInt(email.category_id || "0");
        return catId >= 1 && catId <= 6 && email.status !== "actioned";
      });
      console.log("Normalized emails:", normalizedEmails.length, "New Work emails:", workEmails.length);
      setEmails(workEmails);
    } catch (err) {
      console.error("Email fetch error:", err);
      throw err;
    }
  }

  async function loadSummary() {
    try {
      const summaryData = await fetchEmailSummary();
      setSummary(summaryData);
    } catch (err) {
      console.error("Failed to load summary:", err);
      // Non-critical, continue
    }
  }

  async function loadFolders() {
    try {
      const folderData = await fetchFolders();
      setFolders(folderData);
    } catch (err) {
      console.error("Failed to load folders:", err);
      // Use default folders
      setFolders([
        { id: "operations", name: "operations" },
        { id: "clients", name: "clients" },
        { id: "hr", name: "hr" },
        { id: "finance", name: "finance" },
        { id: "projects", name: "projects" },
      ]);
    }
  }

  async function loadCategories() {
    try {
      // Load Work categories for this tab
      const workCats = await fetchCategories("Work");

      // Add uncategorized option
      const workCatsWithUncategorized = [
        ...workCats,
        {
          id: "uncategorized",
          number: 0,
          label: "Uncategorized",
          master_category: "Work",
          description: "Emails without a category",
          is_system: true,
          icon: "❓",
          color: "#6B7280",
        },
      ];
      setWorkCategories(workCatsWithUncategorized);

      // Load all categories for the picker
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
      await runPipeline();
      await Promise.all([loadEmails(), loadSummary()]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to refresh data"
      );
    } finally {
      setRefreshing(false);
    }
  }

  async function handleEmailChange(emailId: string, updates: Partial<EmailType>) {
    // Special handling for category changes
    if (updates.category_id !== undefined) {
      // Find the target category
      const targetCategory = allCategories.find((cat) => cat.number.toString() === updates.category_id);

      // If moving to Other categories, reclassify immediately
      if (targetCategory && targetCategory.master_category === "Other") {
        try {
          // Start fade-out animation
          setFadingOutEmails((prev) => new Set(prev).add(emailId));

          // Call backend to reclassify
          await reclassifyEmail(emailId, updates.category_id!);

          // Show success toast
          showToast(`Moved to Other → ${targetCategory.label}`, "success");

          // After animation, remove from list
          setTimeout(() => {
            setEmails((prev) => prev.filter((email) => email.id !== emailId));
            setFadingOutEmails((prev) => {
              const newSet = new Set(prev);
              newSet.delete(emailId);
              return newSet;
            });
            // Remove any pending changes for this email
            setPendingChanges((prev) => {
              const newChanges = new Map(prev);
              newChanges.delete(emailId);
              return newChanges;
            });
          }, 300); // Match animation duration

          return; // Don't add to pending changes
        } catch (err) {
          console.error("Failed to reclassify email:", err);
          showToast(
            err instanceof Error ? err.message : "Failed to reclassify email",
            "error"
          );
          setFadingOutEmails((prev) => {
            const newSet = new Set(prev);
            newSet.delete(emailId);
            return newSet;
          });
          return;
        }
      }
    }

    // For other changes (due_date, folder, category 1-5), add to pending changes
    setPendingChanges((prev) => {
      const newChanges = new Map(prev);
      const existing = newChanges.get(emailId) || {};
      newChanges.set(emailId, { ...existing, ...updates });
      return newChanges;
    });

    // Optimistically update the email in the list
    setEmails((prev) =>
      prev.map((email) =>
        email.id === emailId ? { ...email, ...updates } : email
      )
    );
  }

  async function handleApprove(emailId: string, shouldApprove: boolean) {
    try {
      const email = emails.find((e) => e.id === emailId);
      if (!email) return;

      if (shouldApprove) {
        // Get pending changes or current values
        const changes = pendingChanges.get(emailId) || {};
        const metadata = {
          due_date: changes.due_date !== undefined ? changes.due_date : email.due_date,
          category_id: changes.category_id ? parseInt(changes.category_id) : parseInt(email.category_id || "0"),
          folder: changes.folder !== undefined ? changes.folder : email.folder,
          assigned_to: changes.assigned_to !== undefined ? changes.assigned_to : email.assigned_to,
        };

        await approveEmail(emailId, metadata);
        setApprovedEmails((prev) => new Set(prev).add(emailId));
        setPendingChanges((prev) => {
          const newChanges = new Map(prev);
          newChanges.delete(emailId);
          return newChanges;
        });
        showToast("Email approved", "success");
      } else {
        await unapproveEmail(emailId);
        setApprovedEmails((prev) => {
          const newSet = new Set(prev);
          newSet.delete(emailId);
          return newSet;
        });
        showToast("Approval reverted", "success");
      }
      setOpenEmailId(null);
    } catch (err) {
      console.error("Failed to approve/unapprove email:", err);
      showToast(
        err instanceof Error ? err.message : "Failed to process approval",
        "error"
      );
    }
  }

  async function handleApproveAll() {
    try {
      const unapprovedEmails = emails.filter((email) => !approvedEmails.has(email.id));

      for (const email of unapprovedEmails) {
        const changes = pendingChanges.get(email.id) || {};
        const metadata = {
          due_date: changes.due_date !== undefined ? changes.due_date : email.due_date,
          category_id: changes.category_id ? parseInt(changes.category_id) : parseInt(email.category_id || "0"),
          folder: changes.folder !== undefined ? changes.folder : email.folder,
          assigned_to: changes.assigned_to !== undefined ? changes.assigned_to : email.assigned_to,
        };

        await approveEmail(email.id, metadata);
        setApprovedEmails((prev) => new Set(prev).add(email.id));
      }

      setPendingChanges(new Map());
      showToast(`Approved ${unapprovedEmails.length} emails`, "success");
    } catch (err) {
      console.error("Failed to approve all emails:", err);
      showToast(
        err instanceof Error ? err.message : "Failed to approve all",
        "error"
      );
    }
  }

  async function handleExecuteAll() {
    const approvedCount = approvedEmails.size;
    if (approvedCount === 0) {
      showToast("No approved emails to execute", "warning");
      return;
    }

    if (!confirm(`Execute ${approvedCount} approved items? This will move emails to folders and create To-Do tasks.`)) {
      return;
    }

    try {
      setIsExecuting(true);
      const result = await executeApprovedEmails();

      // Show summary
      setExecutionSummary({
        executed: result.executed,
        folders_moved: result.folders_moved,
        todos_created: result.todos_created,
      });

      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        setExecutionSummary(null);
      }, 5000);

      // Fade out approved emails
      approvedEmails.forEach((emailId) => {
        setFadingOutEmails((prev) => new Set(prev).add(emailId));
      });

      // Remove them after animation
      setTimeout(() => {
        setEmails((prev) => prev.filter((email) => !approvedEmails.has(email.id)));
        setApprovedEmails(new Set());
        setFadingOutEmails(new Set());
      }, 300);

      showToast(`${result.executed} items executed ✔`, "success");

      // Refetch data
      await Promise.all([loadEmails(), loadSummary()]);
    } catch (err) {
      console.error("Failed to execute emails:", err);
      showToast(
        err instanceof Error ? err.message : "Failed to execute",
        "error"
      );
    } finally {
      setIsExecuting(false);
    }
  }

  function handleToggle(emailId: string) {
    setOpenEmailId((prev) => (prev === emailId ? null : emailId));
  }

  async function handleCreateFolder(name: string) {
    try {
      const newFolder = await apiCreateFolder(name);
      setFolders((prev) => [...prev, newFolder]);
    } catch (err) {
      // Fallback: add locally
      const newFolder: Folder = {
        id: name.toLowerCase().replace(/\s+/g, "-"),
        name: name.toLowerCase(),
      };
      setFolders((prev) => [...prev, newFolder]);
    }
  }

  // Group emails by category
  function groupByCategory(emails: Email[]): Map<string, Email[]> {
    const groups = new Map<string, Email[]>();

    workCategories.forEach((cat) => {
      groups.set(cat.number.toString(), []);
    });

    emails.forEach((email) => {
      const catId = email.category_id || "0"; // 0 for uncategorized
      if (groups.has(catId)) {
        groups.get(catId)!.push(email);
      } else {
        // If category doesn't exist in our list, add to uncategorized
        if (groups.has("0")) {
          groups.get("0")!.push(email);
        }
      }
    });

    // Sort each group by urgency_score descending
    groups.forEach((emailList) => {
      emailList.sort((a, b) => b.urgency_score - a.urgency_score);
    });

    return groups;
  }

  // Group emails by due date
  function groupByDueDate(emails: Email[]): Map<DateGroup, Email[]> {
    const now = new Date();
    now.setHours(0, 0, 0, 0);

    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const endOfWeek = new Date(now);
    endOfWeek.setDate(endOfWeek.getDate() + (7 - now.getDay()));

    const nextWeekEnd = new Date(endOfWeek);
    nextWeekEnd.setDate(nextWeekEnd.getDate() + 7);

    const groups = new Map<DateGroup, Email[]>([
      ["today", []],
      ["tomorrow", []],
      ["this_week", []],
      ["next_week", []],
      ["no_date", []],
    ]);

    emails.forEach((email) => {
      if (!email.due_date) {
        groups.get("no_date")!.push(email);
        return;
      }

      const dueDate = new Date(email.due_date);
      dueDate.setHours(0, 0, 0, 0);

      if (dueDate.getTime() === now.getTime()) {
        groups.get("today")!.push(email);
      } else if (dueDate.getTime() === tomorrow.getTime()) {
        groups.get("tomorrow")!.push(email);
      } else if (dueDate <= endOfWeek) {
        groups.get("this_week")!.push(email);
      } else if (dueDate <= nextWeekEnd) {
        groups.get("next_week")!.push(email);
      } else {
        groups.get("no_date")!.push(email);
      }
    });

    // Sort each group by urgency_score descending
    groups.forEach((emailList) => {
      emailList.sort((a, b) => b.urgency_score - a.urgency_score);
    });

    return groups;
  }

  // Render loading state
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-center py-24">
          <div className="text-center">
            <RefreshCw className="w-8 h-8 text-[#8888a8] animate-spin mx-auto mb-4" />
            <p className="text-[#8888a8]">Loading work items...</p>
          </div>
        </div>
      </div>
    );
  }

  // Render unauthenticated state
  if (isAuthenticated === false) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-[#16163a] bg-[#13132d] p-12 text-center">
          <h2 className="mb-4 text-xl font-semibold text-[#E0E0EE]">
            Connect Your Outlook Account
          </h2>
          <p className="mb-6 text-[#8888a8]">
            To start triaging your emails, please connect your Microsoft Outlook
            account.
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

  const workCount = summary?.work || emails.length;
  const categoryGroups = groupByCategory(emails);
  const dueDateGroups = groupByDueDate(emails);
  const pendingCount = pendingChanges.size;

  return (
    <>
      <Toast toasts={toasts} onDismiss={dismissToast} />
      <div className="space-y-4">
      {/* Header Bar */}
      <div className="rounded-lg border border-[#16163a] bg-[#13132d] p-4">
        <div className="flex items-center justify-between">
          {/* Left: Title + Count */}
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-[#E0E0EE]">New Mail / Work</h1>
            <span className="px-2.5 py-1 text-sm font-bold bg-[#10B981] text-white rounded">
              {workCount}
            </span>
            {userName && (
              <span className="text-sm text-[#8888a8]">· {userName}</span>
            )}
          </div>

          {/* Center: Sort Toggle */}
          <div className="flex items-center gap-2 bg-[#16163a] rounded-lg p-1">
            <button
              onClick={() => setSortMode("category")}
              className={`px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                sortMode === "category"
                  ? "bg-[#3B82F6] text-white"
                  : "text-[#8888a8] hover:text-[#E0E0EE]"
              }`}
            >
              By Category
            </button>
            <button
              onClick={() => setSortMode("due_date")}
              className={`px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                sortMode === "due_date"
                  ? "bg-[#3B82F6] text-white"
                  : "text-[#8888a8] hover:text-[#E0E0EE]"
              }`}
            >
              By Due Date
            </button>
          </div>

          {/* Right: Action Buttons + Pending Changes Counter */}
          <div className="flex items-center gap-3">
            {pendingCount > 0 && (
              <span className="text-sm font-medium text-[#F59E0B]">
                {pendingCount} unsaved change{pendingCount !== 1 ? "s" : ""}
              </span>
            )}
            {approvedEmails.size > 0 && (
              <span className="text-sm font-medium text-green-500">
                {approvedEmails.size} approved
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#E0E0EE] bg-[#16163a] hover:bg-[#1a1a3a] rounded transition-colors disabled:opacity-50"
            >
              <RefreshCw
                size={16}
                className={refreshing ? "animate-spin" : ""}
              />
              Refresh
            </button>
            <button
              onClick={handleApproveAll}
              disabled={emails.length === approvedEmails.size}
              className="px-3 py-2 text-sm font-medium text-[#E0E0EE] hover:text-green-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Approve All
            </button>
            <button
              onClick={handleExecuteAll}
              disabled={approvedEmails.size === 0 || isExecuting}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-[#10B981] hover:bg-[#059669] rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isExecuting ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  Executing...
                </>
              ) : (
                <>
                  <Play size={16} />
                  Execute All
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Execution Summary Panel */}
      {executionSummary && (
        <div className="rounded-lg border border-green-500 bg-green-500/10 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-green-500 text-2xl">✓</div>
              <div>
                <p className="text-sm font-semibold text-green-500">
                  {executionSummary.executed} items executed successfully
                </p>
                <p className="text-xs text-[#8888a8]">
                  {executionSummary.folders_moved} moved to folders, {executionSummary.todos_created} To-Do tasks created
                </p>
              </div>
            </div>
            <button
              onClick={() => setExecutionSummary(null)}
              className="text-green-500 hover:text-green-400 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Error Banner */}
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

      {/* Empty State */}
      {emails.length === 0 ? (
        <div className="rounded-lg border border-[#16163a] bg-[#13132d] p-16 text-center">
          <div className="text-6xl mb-4">🎉</div>
          <h2 className="text-2xl font-semibold text-[#E0E0EE] mb-2">
            Inbox Zero — nice work!
          </h2>
          <p className="text-[#8888a8]">
            No work items to process. Take a break!
          </p>
        </div>
      ) : sortMode === "category" ? (
        // Category View
        <div className="space-y-6">
          {workCategories.map((category) => {
            const categoryEmails = categoryGroups.get(category.number.toString()) || [];
            if (categoryEmails.length === 0) return null;

            return (
              <div
                key={category.id}
                className="mb-8 rounded-lg border border-[#16163a] border-l-4"
                style={{
                  borderLeftColor: category.color,
                  backgroundColor: `${category.color}15`,
                }}
              >
                {/* Category Header */}
                <div className="flex items-center gap-3 px-4 py-2 border-b border-[#16163a]">
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center text-white text-sm"
                    style={{ backgroundColor: category.color }}
                  >
                    {category.icon}
                  </div>
                  <h3 className="text-base font-semibold text-[#E0E0EE]">
                    {category.number}. {category.label}
                  </h3>
                  <span className="px-2 py-0.5 text-xs font-bold bg-[#16163a] text-[#8888a8] rounded">
                    {categoryEmails.length}
                  </span>
                </div>

                {/* Category Emails */}
                <div className="space-y-2 p-3">
                  {categoryEmails.map((email) => (
                    <EmailRow
                      key={email.id}
                      email={email as EmailType}
                      categories={allCategories}
                      folders={folders}
                      isOpen={openEmailId === email.id}
                      onToggle={() => handleToggle(email.id)}
                      onApprove={(shouldApprove) => handleApprove(email.id, shouldApprove)}
                      onChange={(updates) => handleEmailChange(email.id, updates)}
                      onCreateFolder={handleCreateFolder}
                      isApproved={approvedEmails.has(email.id)}
                      hasUnsavedChanges={pendingChanges.has(email.id)}
                      isFadingOut={fadingOutEmails.has(email.id)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        // Due Date View
        <div className="space-y-6">
          {[
            {
              key: "today" as DateGroup,
              label: "Today",
              color: "#10B981",
              icon: "🔥",
            },
            {
              key: "tomorrow" as DateGroup,
              label: "Tomorrow",
              color: "#3B82F6",
              icon: "📅",
            },
            {
              key: "this_week" as DateGroup,
              label: "This Week",
              color: "#F59E0B",
              icon: "📆",
            },
            {
              key: "next_week" as DateGroup,
              label: "Next Week",
              color: "#6B7280",
              icon: "📋",
            },
            {
              key: "no_date" as DateGroup,
              label: "No Date",
              color: "#555577",
              icon: "📌",
            },
          ].map((group) => {
            const groupEmails = dueDateGroups.get(group.key) || [];
            if (groupEmails.length === 0) return null;

            return (
              <div
                key={group.key}
                className="mb-8 rounded-lg border border-[#16163a] border-l-4"
                style={{
                  borderLeftColor: group.color,
                  backgroundColor: `${group.color}15`,
                }}
              >
                {/* Date Group Header */}
                <div className="flex items-center gap-3 px-4 py-2 border-b border-[#16163a]">
                  <span className="text-xl">{group.icon}</span>
                  <h3 className="text-base font-semibold text-[#E0E0EE]">
                    {group.label}
                  </h3>
                  <span className="px-2 py-0.5 text-xs font-bold bg-[#16163a] text-[#8888a8] rounded">
                    {groupEmails.length}
                  </span>
                </div>

                {/* Group Emails */}
                <div className="space-y-2 p-3">
                  {groupEmails.map((email) => (
                    <EmailRow
                      key={email.id}
                      email={email as EmailType}
                      categories={allCategories}
                      folders={folders}
                      isOpen={openEmailId === email.id}
                      onToggle={() => handleToggle(email.id)}
                      onApprove={(shouldApprove) => handleApprove(email.id, shouldApprove)}
                      onChange={(updates) => handleEmailChange(email.id, updates)}
                      onCreateFolder={handleCreateFolder}
                      isApproved={approvedEmails.has(email.id)}
                      hasUnsavedChanges={pendingChanges.has(email.id)}
                      isFadingOut={fadingOutEmails.has(email.id)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      </div>
    </>
  );
}
