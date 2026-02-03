"use client";

import { useEffect, useState } from "react";
import { RefreshCw, CheckCheck } from "lucide-react";
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
  confirmOtherEmails,
  approveEmail,
  executeApprovedEmails,
  batchMoveToFolder,
  batchDeleteCategory,
  type Email,
  type EmailSummary,
  type AuthResponse,
} from "@/lib/api";

export default function OtherPage() {
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [userName, setUserName] = useState<string>("");

  // Data state
  const [emails, setEmails] = useState<Email[]>([]);
  const [summary, setSummary] = useState<EmailSummary | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [otherCategories, setOtherCategories] = useState<Category[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Email interaction state
  const [openEmailId, setOpenEmailId] = useState<string | null>(null);
  const [approvedEmails, setApprovedEmails] = useState<Set<string>>(new Set());
  const [pendingChanges, setPendingChanges] = useState<Map<string, Partial<Email>>>(
    new Map()
  );
  const [fadingOutEmails, setFadingOutEmails] = useState<Set<string>>(new Set());

  // Confirmation state
  const [isConfirming, setIsConfirming] = useState(false);
  const [confirmationSummary, setConfirmationSummary] = useState<{
    confirmed: number;
    moved: number;
  } | null>(null);

  // Batch action state
  const [pendingBatchAction, setPendingBatchAction] = useState<{
    categoryId: number;
    categoryLabel: string;
    action: 'move' | 'delete';
  } | null>(null);
  const [batchProcessing, setBatchProcessing] = useState(false);

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
      // Fetch all emails
      const result = await fetchEmails();

      console.log("Fetched emails result:", result);

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
        recommended_folder: email.recommended_folder || null,
        folder_is_new: email.folder_is_new || false,
      }));

      // Filter for New Mail > Other (unactioned emails with Other categories 7-13)
      const otherEmails = normalizedEmails.filter((email) => {
        const catId = parseInt(email.category_id || "0");
        return email.status !== "actioned" && catId >= 7;
      });

      console.log("Other emails:", otherEmails.length);

      // Debug: Log category distribution
      const categoryDistribution = otherEmails.reduce((acc, email) => {
        const catId = email.category_id || "null";
        acc[catId] = (acc[catId] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      console.log("Category distribution:", categoryDistribution);

      setEmails(otherEmails);

      // Auto-fetch folder recommendations for FYI - Group emails (category 7) without recommendations
      const fyiGroupEmails = otherEmails.filter(
        (email) => email.category_id === "7" && !email.recommended_folder
      );

      console.log(`Found ${fyiGroupEmails.length} FYI - Group emails (category 7) without recommendations`);

      if (fyiGroupEmails.length > 0) {
        console.log("Sample FYI email:", JSON.stringify(fyiGroupEmails[0], null, 2));

        // Fetch recommendations in the background
        fyiGroupEmails.forEach(async (email) => {
          try {
            console.log(`Fetching recommendation for email ${email.id}...`);
            const response = await fetch(
              `http://localhost:8000/api/folders/recommend-single/${email.id}`,
              {
                method: "POST",
                credentials: "include"
              }
            );

            console.log(`Response status for email ${email.id}: ${response.status}`);

            if (response.ok) {
              const data = await response.json();
              console.log(`Got recommendation for email ${email.id}:`, data);

              // Update the email with the recommendation
              setEmails((prev) =>
                prev.map((e) =>
                  e.id === email.id
                    ? {
                        ...e,
                        recommended_folder: data.recommended_folder,
                        folder_is_new: data.is_new_folder,
                      }
                    : e
                )
              );
            } else {
              const errorText = await response.text();
              console.error(`Failed to get recommendation for email ${email.id}:`, errorText);
            }
          } catch (error) {
            console.error(`Failed to fetch recommendation for email ${email.id}:`, error);
          }
        });
      }
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
    }
  }

  async function loadFolders() {
    try {
      const folderData = await fetchFolders();
      setFolders(folderData);
    } catch (err) {
      console.error("Failed to load folders:", err);
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
      // Load Other categories for this tab
      const otherCats = await fetchCategories("Other");
      setOtherCategories(otherCats);

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

      if (targetCategory) {
        try {
          // Call backend to reclassify immediately for ALL category changes
          console.log(`[handleEmailChange] Reclassifying email ${emailId} to category ${updates.category_id} (${targetCategory.label})`);
          const updatedEmail = await reclassifyEmail(emailId, updates.category_id!);
          console.log(`[handleEmailChange] Backend response:`, updatedEmail);

          // If moving to Work categories, remove from Other list
          if (targetCategory.master_category === "Work") {
            // Start fade-out animation
            setFadingOutEmails((prev) => new Set(prev).add(emailId));

            // Show success toast
            showToast(`Moved to Work → ${targetCategory.label}`, "success");

            // After animation, remove from list
            setTimeout(() => {
              setEmails((prev) => prev.filter((email) => email.id !== emailId));
              setFadingOutEmails((prev) => {
                const newSet = new Set(prev);
                newSet.delete(emailId);
                return newSet;
              });
              setPendingChanges((prev) => {
                const newChanges = new Map(prev);
                newChanges.delete(emailId);
                return newChanges;
              });
            }, 300);

            return;
          } else {
            // Moving within Other categories - update local state with backend response
            console.log(`[handleEmailChange] Updating local state with backend response for email ${emailId}`);
            setEmails((prev) =>
              prev.map((email) =>
                email.id === emailId ? { ...email, ...updatedEmail, category_id: updatedEmail.category_id?.toString() } : email
              )
            );

            // Show success toast
            showToast(`Updated category to ${targetCategory.label}`, "success");

            return;
          }
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

    // For non-category changes, add to pending changes
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

  function handleApprove(emailId: string, shouldApprove: boolean) {
    if (shouldApprove) {
      setApprovedEmails((prev) => new Set(prev).add(emailId));
    } else {
      setApprovedEmails((prev) => {
        const newSet = new Set(prev);
        newSet.delete(emailId);
        return newSet;
      });
    }
    setOpenEmailId(null);
  }

  async function handleConfirmSelected() {
    const selectedCount = approvedEmails.size;
    if (selectedCount === 0) {
      showToast("No items selected. Please check the emails you want to confirm.", "warning");
      return;
    }

    const selectedEmailsList = emails.filter((email) => approvedEmails.has(email.id));
    const emailsWithRecommendations = selectedEmailsList.filter((email) => email.recommended_folder);

    if (!confirm(
      `Confirm ${selectedCount} selected item${selectedCount !== 1 ? "s" : ""}? ` +
      (emailsWithRecommendations.length > 0
        ? `This will file them to their recommended folders.`
        : `This will file them to default folders.`)
    )) {
      return;
    }

    try {
      setIsConfirming(true);
      console.log(`[Confirm Selected] Starting approval for ${selectedCount} emails`);

      // For each approved email, approve it with its metadata
      for (const email of selectedEmailsList) {
        const metadata: any = {
          folder: email.recommended_folder || email.folder,
        };

        console.log(`[Confirm Selected] Approving email ${email.id} with folder: ${metadata.folder}`);

        try {
          const approveResult = await approveEmail(email.id, metadata);
          console.log(`[Confirm Selected] Approved email ${email.id}:`, approveResult);
        } catch (approveErr) {
          console.error(`[Confirm Selected] Failed to approve email ${email.id}:`, approveErr);
          console.error(`[Confirm Selected] Email data:`, JSON.stringify(email, null, 2));
          console.error(`[Confirm Selected] Metadata sent:`, JSON.stringify(metadata, null, 2));
          throw new Error(`Backend error when approving "${email.subject}". Check backend terminal for error details. This is a backend bug that needs to be fixed.`);
        }
      }

      console.log(`[Confirm Selected] All emails approved. Executing...`);

      // Execute the approved emails
      let result;
      try {
        result = await executeApprovedEmails();
        console.log(`[Confirm Selected] Execute result:`, result);
      } catch (executeErr) {
        console.error(`[Confirm Selected] Failed to execute:`, executeErr);
        throw new Error(`Failed to execute approved emails: ${executeErr instanceof Error ? executeErr.message : String(executeErr)}`);
      }

      // Show summary
      setConfirmationSummary({
        confirmed: result.executed,
        moved: result.folders_moved,
      });

      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        setConfirmationSummary(null);
      }, 5000);

      // Fade out selected emails
      approvedEmails.forEach((emailId) => {
        setFadingOutEmails((prev) => new Set(prev).add(emailId));
      });

      // Remove them after animation
      setTimeout(() => {
        setEmails((prev) => prev.filter((email) => !approvedEmails.has(email.id)));
        setApprovedEmails(new Set());
        setFadingOutEmails(new Set());
      }, 300);

      showToast(`${result.executed} items confirmed ✔`, "success");

      // Refetch data
      await Promise.all([loadEmails(), loadSummary()]);
    } catch (err) {
      console.error("[Confirm Selected] Error:", err);
      showToast(
        err instanceof Error ? err.message : "Failed to confirm selected",
        "error"
      );
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleConfirmAll() {
    const itemCount = emails.length;
    if (itemCount === 0) {
      showToast("No Other items to confirm", "warning");
      return;
    }

    if (!confirm(`Confirm ${itemCount} Other items? This will file them to default folders.`)) {
      return;
    }

    try {
      setIsConfirming(true);
      const result = await confirmOtherEmails();

      // Show summary
      setConfirmationSummary({
        confirmed: result.confirmed,
        moved: result.moved,
      });

      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        setConfirmationSummary(null);
      }, 5000);

      // Fade out all emails
      emails.forEach((email) => {
        setFadingOutEmails((prev) => new Set(prev).add(email.id));
      });

      // Remove them after animation
      setTimeout(() => {
        setEmails([]);
        setFadingOutEmails(new Set());
      }, 300);

      showToast(`${result.confirmed} items confirmed ✔`, "success");

      // Refetch data
      await Promise.all([loadEmails(), loadSummary()]);
    } catch (err) {
      console.error("Failed to confirm emails:", err);
      showToast(
        err instanceof Error ? err.message : "Failed to confirm",
        "error"
      );
    } finally {
      setIsConfirming(false);
    }
  }

  function initiateBatchAction(categoryId: number, categoryLabel: string, action: 'move' | 'delete') {
    setPendingBatchAction({ categoryId, categoryLabel, action });
  }

  function cancelBatchAction() {
    setPendingBatchAction(null);
  }

  async function confirmBatchAction() {
    if (!pendingBatchAction) return;

    const { categoryId, categoryLabel, action } = pendingBatchAction;

    try {
      setBatchProcessing(true);
      if (action === 'move') {
        const result = await batchMoveToFolder(categoryId);
        showToast(`${result.moved} emails moved to ${categoryLabel} folder ✓`, "success");
      } else {
        const result = await batchDeleteCategory(categoryId);
        showToast(`${result.deleted} emails moved to trash ✓`, "success");
      }

      // Fade out and remove emails from this category
      const categoryEmails = emails.filter(e => {
        const emailCategory = allCategories.find(c => c.id === e.category_id);
        return emailCategory?.number === categoryId;
      });

      categoryEmails.forEach((email) => {
        setFadingOutEmails((prev) => new Set(prev).add(email.id));
      });

      setTimeout(() => {
        setEmails((prev) => prev.filter(e => {
          const emailCategory = allCategories.find(c => c.id === e.category_id);
          return emailCategory?.number !== categoryId;
        }));
        setFadingOutEmails(new Set());
      }, 300);

      await Promise.all([loadEmails(), loadSummary()]);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Batch action failed", "error");
    } finally {
      setBatchProcessing(false);
      setPendingBatchAction(null);
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

    // Initialize groups for all Other categories
    otherCategories.forEach((cat) => {
      groups.set(cat.number.toString(), []);
    });

    // Distribute emails into groups
    emails.forEach((email) => {
      const catId = email.category_id || "0";
      if (groups.has(catId)) {
        groups.get(catId)!.push(email);
      } else {
        // Unknown category - create a group for it if it doesn't exist
        if (!groups.has(catId)) {
          groups.set(catId, [email]);
        }
      }
    });

    // Sort each group by confidence descending (since urgency may be 0)
    groups.forEach((emailList) => {
      emailList.sort((a, b) => b.confidence - a.confidence);
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
            <p className="text-[#8888a8]">Loading other items...</p>
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

  const otherCount = summary?.noise || emails.length;
  const categoryGroups = groupByCategory(emails);
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
            <h1 className="text-xl font-semibold text-[#E0E0EE]">New Mail / Other</h1>
            <span className="px-2.5 py-1 text-sm font-bold bg-[#3B82F6] text-white rounded">
              {otherCount}
            </span>
            {userName && (
              <span className="text-sm text-[#8888a8]">· {userName}</span>
            )}
          </div>

          {/* Right: Action Buttons + Pending Changes Counter */}
          <div className="flex items-center gap-3">
            {pendingCount > 0 && (
              <span className="text-sm font-medium text-[#F59E0B]">
                {pendingCount} unsaved change{pendingCount !== 1 ? "s" : ""}
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
              onClick={handleConfirmSelected}
              disabled={approvedEmails.size === 0 || isConfirming}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-green-600 hover:bg-green-700 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isConfirming ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  Confirming...
                </>
              ) : (
                <>
                  <CheckCheck size={16} />
                  Confirm Selected ({approvedEmails.size})
                </>
              )}
            </button>
            <button
              onClick={handleConfirmAll}
              disabled={emails.length === 0 || isConfirming}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-[#3B82F6] hover:bg-[#2563EB] rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isConfirming ? (
                <>
                  <RefreshCw size={16} className="animate-spin" />
                  Confirming...
                </>
              ) : (
                <>
                  <CheckCheck size={16} />
                  Confirm All
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Summary Panel */}
      {confirmationSummary && (
        <div className="rounded-lg border border-[#3B82F6] bg-[#3B82F6]/10 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-[#3B82F6] text-2xl">✓</div>
              <div>
                <p className="text-sm font-semibold text-[#3B82F6]">
                  {confirmationSummary.confirmed} items confirmed successfully
                </p>
                <p className="text-xs text-[#8888a8]">
                  {confirmationSummary.moved} moved to folders
                </p>
              </div>
            </div>
            <button
              onClick={() => setConfirmationSummary(null)}
              className="text-[#3B82F6] hover:text-[#2563EB] transition-colors"
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
          <div className="text-6xl mb-4">📭</div>
          <h2 className="text-2xl font-semibold text-[#E0E0EE] mb-2">
            All Clear!
          </h2>
          <p className="text-[#8888a8]">
            No other items to review. Great work!
          </p>
        </div>
      ) : (
        // Category View
        <div className="space-y-6">
          {otherCategories.map((category) => {
            const categoryEmails = categoryGroups.get(category.number.toString()) || [];
            // Don't show empty sections
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
                <div className="flex items-center justify-between px-4 py-2 border-b border-[#16163a]">
                  <div className="flex items-center gap-3">
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

                  {/* Batch Actions for Marketing, Notifications, Calendar Items, and Travel */}
                  {[8, 9, 10, 12].includes(category.number) && (
                    <div className="flex items-center gap-2">
                      {/* Move to Folder Button */}
                      {pendingBatchAction?.categoryId === category.number && pendingBatchAction.action === 'move' ? (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={confirmBatchAction}
                            disabled={batchProcessing}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-green-600 hover:bg-green-700 rounded transition-colors disabled:opacity-50"
                          >
                            <CheckCheck size={14} />
                            Confirm Move
                          </button>
                          <button
                            onClick={cancelBatchAction}
                            disabled={batchProcessing}
                            className="px-3 py-1.5 text-xs font-medium text-[#8888a8] hover:text-white transition-colors disabled:opacity-50"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => initiateBatchAction(category.number, `${category.number}. ${category.label}`, 'move')}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-[#3B82F6] hover:bg-[#2563EB] rounded transition-colors"
                        >
                          Move to Folder
                        </button>
                      )}

                      {/* Delete All Button */}
                      {pendingBatchAction?.categoryId === category.number && pendingBatchAction.action === 'delete' ? (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={confirmBatchAction}
                            disabled={batchProcessing}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded transition-colors disabled:opacity-50"
                          >
                            <CheckCheck size={14} />
                            Confirm Delete
                          </button>
                          <button
                            onClick={cancelBatchAction}
                            disabled={batchProcessing}
                            className="px-3 py-1.5 text-xs font-medium text-[#8888a8] hover:text-white transition-colors disabled:opacity-50"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => initiateBatchAction(category.number, `${category.number}. ${category.label}`, 'delete')}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-[#D94F4F] hover:bg-[#C43F3F] rounded transition-colors"
                        >
                          Delete All
                        </button>
                      )}
                    </div>
                  )}
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
      )}
      </div>
    </>
  );
}
