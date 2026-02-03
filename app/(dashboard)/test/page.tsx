"use client";

import React, { useState } from "react";
import {
  EmailRow,
  CalendarPicker,
  CategoryPicker,
  FolderPicker,
} from "@/components";
import type { Email, Category, Folder } from "@/components";

// 11 System Categories matching TRIAGE design
const DEFAULT_CATS: Category[] = [
  {
    id: "reply",
    name: "Reply",
    icon: "↩️",
    color: "#3B82F6", // blue
  },
  {
    id: "review",
    name: "Review",
    icon: "👀",
    color: "#8B5CF6", // purple
  },
  {
    id: "approve",
    name: "Approve",
    icon: "✓",
    color: "#10B981", // green
  },
  {
    id: "schedule",
    name: "Schedule",
    icon: "📅",
    color: "#F59E0B", // amber
  },
  {
    id: "delegate",
    name: "Delegate",
    icon: "👥",
    color: "#06B6D4", // cyan
  },
  {
    id: "action",
    name: "Action",
    icon: "⚡",
    color: "#EF4444", // red
  },
  {
    id: "file",
    name: "File",
    icon: "📁",
    color: "#6B7280", // gray
  },
  {
    id: "read",
    name: "Read",
    icon: "📖",
    color: "#EC4899", // pink
  },
  {
    id: "wait",
    name: "Wait",
    icon: "⏳",
    color: "#F97316", // orange
  },
  {
    id: "info",
    name: "Info",
    icon: "ℹ️",
    color: "#14B8A6", // teal
  },
  {
    id: "noise",
    name: "Noise",
    icon: "🔇",
    color: "#64748B", // slate
  },
];

// Mock folders
const MOCK_FOLDERS: Folder[] = [
  { id: "operations", name: "operations" },
  { id: "clients", name: "clients" },
  { id: "hr", name: "hr" },
  { id: "finance", name: "finance" },
  { id: "projects", name: "projects" },
];

// Mock emails with different urgency levels
const MOCK_EMAILS: Email[] = [
  // High urgency email
  {
    id: "email-1",
    message_id: "msg-001",
    from_address: "ceo@company.com",
    from_name: "Sarah Chen (CEO)",
    subject: "URGENT: Board meeting materials needed by EOD",
    body_preview:
      "Hi team, I need the Q4 financial reports and the new product roadmap slides for tomorrow's board meeting. This is blocking the entire agenda. Please prioritize.\n\nThe board members are expecting these materials tonight for their review. We cannot proceed without them.\n\nLet me know if there are any blockers.",
    received_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(), // 45 minutes ago
    importance: "high",
    conversation_id: "conv-001",
    has_attachments: false,
    category_id: "action",
    confidence: 0.95,
    urgency_score: 92,
    due_date: new Date().toISOString().split("T")[0], // today
    folder: null,
    status: "pending",
    floor_override: true,
    stale_days: 0,
    todo_task_id: null,
    aiDraft: {
      tone: "urgent",
      text: "Hi Sarah,\n\nI'm on it. I'll have the Q4 financial reports compiled within the next 2 hours. The product roadmap slides are already 80% complete - I'll finalize and send both documents by 4 PM today.\n\nNo blockers on my end. I'll keep you posted on progress.\n\nBest,",
      citations: [
        {
          highlight: "Q4 financial reports",
          text: "Referenced from original email request",
        },
        {
          highlight: "4 PM today",
          text: "Based on 'EOD' deadline in subject line",
        },
      ],
    },
  },
  // Medium urgency email
  {
    id: "email-2",
    message_id: "msg-002",
    from_address: "john@vendor.com",
    from_name: "John Martinez",
    subject: "Re: Contract renewal discussion",
    body_preview:
      "Thanks for your previous response. I wanted to follow up on the contract renewal we discussed last week. Our current agreement expires in 45 days.\n\nCould we schedule a call next week to go over the updated terms? I've attached our proposed pricing for the next year.\n\nLooking forward to continuing our partnership.",
    received_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(), // 5 hours ago
    importance: "normal",
    conversation_id: "conv-002",
    has_attachments: true,
    category_id: "schedule",
    confidence: 0.82,
    urgency_score: 55,
    due_date: "2026-02-10",
    folder: "operations",
    status: "pending",
    floor_override: false,
    stale_days: 0,
    todo_task_id: null,
  },
  // Low urgency email
  {
    id: "email-3",
    message_id: "msg-003",
    from_address: "newsletter@techcompany.com",
    from_name: "TechCompany Newsletter",
    subject: "Your weekly digest: Top 10 productivity tips",
    body_preview:
      "Hello! Here's your personalized weekly digest with the most popular articles from this week:\n\n1. 10 ways to optimize your morning routine\n2. The science of deep work\n3. New productivity apps to try in 2026\n\nPlus exclusive deals on our premium courses.",
    received_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(), // 2 days ago
    importance: "low",
    conversation_id: "conv-003",
    has_attachments: false,
    category_id: "read",
    confidence: 0.68,
    urgency_score: 18,
    due_date: null,
    folder: null,
    status: "pending",
    floor_override: false,
    stale_days: 0,
    todo_task_id: null,
  },
];

export default function TestPage() {
  // State for email rows
  const [emails, setEmails] = useState(MOCK_EMAILS);
  const [openEmailIds, setOpenEmailIds] = useState<Set<string>>(new Set());
  const [doneEmailIds, setDoneEmailIds] = useState<Set<string>>(new Set());

  // State for standalone pickers
  const [testDate, setTestDate] = useState<string | null>("2026-02-05");
  const [testCategory, setTestCategory] = useState<string | null>("reply");
  const [testFolder, setTestFolder] = useState<string | null>("operations");
  const [folders, setFolders] = useState(MOCK_FOLDERS);

  const handleToggleEmail = (emailId: string) => {
    setOpenEmailIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(emailId)) {
        newSet.delete(emailId);
      } else {
        newSet.add(emailId);
      }
      return newSet;
    });
  };

  const handleApproveEmail = (emailId: string) => {
    setDoneEmailIds((prev) => new Set(prev).add(emailId));
    console.log(`Email ${emailId} approved`);
  };

  const handleChangeEmail = (emailId: string, updates: Partial<Email>) => {
    setEmails((prev) =>
      prev.map((email) =>
        email.id === emailId ? { ...email, ...updates } : email
      )
    );
    console.log(`Email ${emailId} updated:`, updates);
  };

  const handleCreateFolder = (name: string) => {
    const newFolder: Folder = {
      id: name.toLowerCase().replace(/\s+/g, "-"),
      name: name.toLowerCase(),
    };
    setFolders((prev) => [...prev, newFolder]);
    console.log(`Created folder: ${name}`);
  };

  return (
    <div className="min-h-screen bg-[#0a0a1a] p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-[#E0E0EE] mb-2">
            TRIAGE Component Test Page
          </h1>
          <p className="text-[#8888a8]">
            Testing EmailRow, CalendarPicker, CategoryPicker, and FolderPicker
            components
          </p>
        </div>

        {/* Email Rows Section */}
        <section>
          <h2 className="text-xl font-semibold text-[#E0E0EE] mb-4">
            Email Rows
          </h2>
          <div className="space-y-4">
            {emails.map((email) => (
              <EmailRow
                key={email.id}
                email={email}
                categories={DEFAULT_CATS}
                folders={folders}
                isOpen={openEmailIds.has(email.id)}
                onToggle={() => handleToggleEmail(email.id)}
                onApprove={() => handleApproveEmail(email.id)}
                onChange={(updates) => handleChangeEmail(email.id, updates)}
                onCreateFolder={handleCreateFolder}
                isDone={doneEmailIds.has(email.id)}
              />
            ))}
          </div>
        </section>

        {/* Standalone Components Section */}
        <section>
          <h2 className="text-xl font-semibold text-[#E0E0EE] mb-4">
            Standalone Pickers
          </h2>
          <div className="bg-[#13132d] border border-[#16163a] rounded-lg p-6 space-y-6">
            {/* Calendar Picker */}
            <div>
              <h3 className="text-sm font-semibold text-[#E0E0EE] mb-2">
                CalendarPicker
              </h3>
              <div className="flex items-center gap-4">
                <CalendarPicker value={testDate} onChange={setTestDate} />
                <span className="text-sm text-[#8888a8]">
                  Selected: {testDate || "No date selected"}
                </span>
              </div>
            </div>

            {/* Category Picker */}
            <div>
              <h3 className="text-sm font-semibold text-[#E0E0EE] mb-2">
                CategoryPicker
              </h3>
              <div className="flex items-center gap-4">
                <CategoryPicker
                  categories={DEFAULT_CATS}
                  value={testCategory}
                  onChange={setTestCategory}
                />
                <span className="text-sm text-[#8888a8]">
                  Selected:{" "}
                  {DEFAULT_CATS.find((c) => c.id === testCategory)?.name ||
                    "None"}
                </span>
              </div>
            </div>

            {/* Folder Picker */}
            <div>
              <h3 className="text-sm font-semibold text-[#E0E0EE] mb-2">
                FolderPicker
              </h3>
              <div className="flex items-center gap-4">
                <FolderPicker
                  folders={folders}
                  value={testFolder}
                  onChange={setTestFolder}
                  onCreateFolder={handleCreateFolder}
                />
                <span className="text-sm text-[#8888a8]">
                  Selected: {testFolder || "None"}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Categories Reference */}
        <section>
          <h2 className="text-xl font-semibold text-[#E0E0EE] mb-4">
            11 System Categories
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {DEFAULT_CATS.map((category) => (
              <div
                key={category.id}
                className="bg-[#13132d] border border-[#16163a] rounded-lg p-3 flex items-center gap-3"
              >
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center text-white shrink-0"
                  style={{ backgroundColor: category.color }}
                >
                  {category.icon}
                </div>
                <div>
                  <div className="text-sm font-medium text-[#E0E0EE]">
                    {category.name}
                  </div>
                  <div className="text-xs text-[#8888a8]">{category.id}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
