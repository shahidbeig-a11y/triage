"use client";

import React from "react";
import { Check, ChevronDown } from "lucide-react";
import UrgencyBar from "./UrgencyBar";
import ConfidenceDot from "./ConfidenceDot";
import CalendarPicker from "./CalendarPicker";
import CategoryPicker from "./CategoryPicker";
import FolderPicker from "./FolderPicker";
import { Email, Category, Folder } from "./types";

interface EmailRowProps {
  email: Email;
  categories: Category[];
  folders: Folder[];
  isOpen: boolean;
  onToggle: () => void;
  onApprove: (isApproved: boolean) => void;
  onChange: (updates: Partial<Email>) => void;
  onCreateFolder: (name: string) => void;
  isApproved: boolean;
  hasUnsavedChanges?: boolean;
  isFadingOut?: boolean;
}

export default function EmailRow({
  email,
  categories,
  folders,
  isOpen,
  onToggle,
  onApprove,
  onChange,
  onCreateFolder,
  isApproved,
  hasUnsavedChanges = false,
  isFadingOut = false,
}: EmailRowProps) {
  // Find the category for this email - match by number since category_id is stored as number
  const category = categories.find((cat) => cat.number.toString() === email.category_id?.toString());

  // Check if recommended folder is new (doesn't exist in folders list)
  const isRecommendedFolderNew = email.recommended_folder && !folders.some(
    (folder) => folder.name.toLowerCase() === email.recommended_folder?.toLowerCase()
  );

  // Format timestamp
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      className={`
        relative border border-[#16163a] rounded-lg overflow-visible
        ${isApproved ? "border-l-4 border-l-green-500 bg-green-500/10" : ""}
        ${!isApproved ? "hover:bg-[#1a1a3a]/50" : ""}
        ${hasUnsavedChanges && !isApproved ? "border-l-4 border-l-[#F59E0B]" : ""}
        ${isFadingOut ? "opacity-0 scale-95 transition-all duration-300" : ""}
      `}
      style={{
        backgroundColor: isApproved ? undefined : "#13132d",
        zIndex: isOpen ? 9999 : "auto"
      }}
    >
      {/* Main row */}
      <div
        className="p-3 cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex items-center gap-4">
          {/* Left section: Confidence + Category + Unsaved Indicator */}
          <div className="flex items-center gap-2 min-w-fit shrink-0">
            <ConfidenceDot confidence={email.confidence} />
            {category && (
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs"
                style={{ backgroundColor: category.color }}
              >
                {category.icon}
              </div>
            )}
          </div>

          {/* Center section: Email details */}
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-0.5">
              <span className="text-sm font-semibold text-[#E0E0EE] truncate">
                {email.from_name}
              </span>
              <span className="text-[10px] text-[#8888a8]">
                {formatTime(email.received_at)}
              </span>
              {hasUnsavedChanges && (
                <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase bg-[#3B82F6] text-white rounded animate-pulse">
                  Unsaved
                </span>
              )}
            </div>
            <div className="text-xs text-[#E0E0EE] truncate mb-0.5">
              {email.subject}
            </div>
            <div className="flex items-center gap-2">
              <div className="text-[10px] text-[#8888a8] truncate flex-1">
                {email.body_preview}
              </div>
              {/* Show AI recommended folder badge for FYI - Group emails */}
              {category && (category.number === 7 || category.number === "7" || category.label === "FYI - Group") && email.recommended_folder && (
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-purple-500/10 rounded-md border border-purple-500/20 shrink-0">
                  <span className="text-sm">✨</span>
                  <span className="text-xs text-purple-300 font-medium">
                    File to:
                  </span>
                  <span className="text-xs text-purple-100 font-semibold">
                    {email.recommended_folder}
                  </span>
                  {isRecommendedFolderNew && (
                    <span className="text-[9px] bg-purple-500/30 text-purple-200 px-1.5 py-0.5 rounded font-bold">
                      NEW
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right section: UrgencyBar + Actions */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-48">
              <UrgencyBar
                score={email.urgency_score}
                staleDays={email.stale_days}
                floorOverride={email.floor_override}
              />
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2">
              <CalendarPicker
                value={email.due_date}
                onChange={(date) => onChange({ due_date: date })}
              />
              <CategoryPicker
                categories={categories}
                value={email.category_id}
                onChange={(categoryId) => onChange({ category_id: categoryId })}
              />
              <FolderPicker
                folders={folders}
                value={email.folder}
                onChange={(folder) => onChange({ folder })}
                onCreateFolder={onCreateFolder}
              />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove(!isApproved);
                }}
                className={`p-1.5 rounded transition-all ${
                  isApproved
                    ? "bg-green-500 text-white hover:bg-green-600"
                    : hasUnsavedChanges
                    ? "bg-[#3B82F6] text-white hover:bg-[#2563EB] shadow-lg shadow-[#3B82F6]/50 animate-pulse"
                    : "hover:bg-green-500/20 text-[#8888a8] hover:text-green-500"
                }`}
                title={isApproved ? "Unapprove" : hasUnsavedChanges ? "Save & Approve" : "Approve"}
              >
                <Check size={16} className={isApproved ? "stroke-[3]" : ""} />
              </button>
            </div>

            {/* Expand/collapse chevron */}
            <ChevronDown
              size={16}
              className={`text-[#8888a8] transition-transform ${
                isOpen ? "rotate-180" : ""
              }`}
            />
          </div>
        </div>
      </div>

      {/* Expanded section */}
      {isOpen && (
        <div className="border-t border-[#16163a] p-4 bg-[#13132d]">
          {/* Email body preview */}
          <div className="mb-4">
            <h4 className="text-sm font-semibold text-[#E0E0EE] mb-2">
              Email Preview
            </h4>
            <div className="text-sm text-[#8888a8] whitespace-pre-wrap max-h-48 overflow-y-auto">
              {email.body_preview}
            </div>
          </div>

          {/* Assigned To field for Discuss (4) and Delegate (5) categories */}
          {category && (category.number === 4 || category.number === 5) && (
            <div className="mb-4 border-t border-[#16163a] pt-4">
              <label className="block text-sm font-semibold text-[#E0E0EE] mb-2">
                {category.number === 4 ? "Discuss with:" : "Delegate to:"}
              </label>
              <input
                type="text"
                value={email.assigned_to || ""}
                onChange={(e) => {
                  e.stopPropagation();
                  onChange({ assigned_to: e.target.value });
                }}
                onClick={(e) => e.stopPropagation()}
                placeholder="Enter person's name..."
                className="w-full px-3 py-2 bg-[#16163a] text-[#E0E0EE] text-sm rounded border border-[#16163a] focus:border-[#3B82F6] focus:outline-none"
              />
            </div>
          )}

          {/* Folder Recommendation for FYI - Group (7) */}
          {category && (category.number === 7 || category.number === "7" || category.label === "FYI - Group") && (
            <div className="mb-4 border-t border-[#16163a] pt-4">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-semibold text-[#E0E0EE]">
                  📁 File to Folder:
                </label>
                {!email.recommended_folder && (
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      // Trigger AI recommendation
                      try {
                        const response = await fetch(`http://localhost:8000/api/folders/recommend-single/${email.id}`, {
                          method: 'POST'
                        });
                        if (response.ok) {
                          const data = await response.json();
                          onChange({
                            recommended_folder: data.recommended_folder,
                            folder_is_new: data.is_new_folder
                          });
                        }
                      } catch (error) {
                        console.error('Failed to get folder recommendation:', error);
                      }
                    }}
                    className="text-xs px-2 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded transition-colors"
                  >
                    ✨ Get AI Recommendation
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={email.recommended_folder || email.folder || ""}
                  onChange={(e) => {
                    e.stopPropagation();
                    onChange({ recommended_folder: e.target.value });
                  }}
                  onClick={(e) => e.stopPropagation()}
                  placeholder="Enter folder name (e.g., Projects/Marketing)..."
                  className="flex-1 px-3 py-2 bg-[#16163a] text-[#E0E0EE] text-sm rounded border border-[#16163a] focus:border-[#3B82F6] focus:outline-none"
                />
                {isRecommendedFolderNew && (
                  <span className="text-xs bg-purple-500/20 text-purple-300 px-2 py-1 rounded shrink-0">
                    NEW FOLDER
                  </span>
                )}
              </div>

              {email.recommended_folder && (
                <p className="text-xs text-gray-400 mt-2 italic">
                  AI will create this folder if it doesn't exist when you execute
                </p>
              )}
            </div>
          )}

          {/* AI Draft section */}
          {email.aiDraft && (
            <div className="border-t border-[#16163a] pt-4">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="text-sm font-semibold text-[#E0E0EE]">
                  AI Generated Draft
                </h4>
                <span className="px-2 py-0.5 text-xs rounded bg-[#16163a] text-[#8888a8] uppercase">
                  {email.aiDraft.tone}
                </span>
              </div>
              <div className="text-sm text-[#E0E0EE] whitespace-pre-wrap bg-[#16163a]/30 p-3 rounded">
                {email.aiDraft.text}
              </div>
              {email.aiDraft.citations && email.aiDraft.citations.length > 0 && (
                <div className="mt-3">
                  <h5 className="text-xs font-semibold text-[#8888a8] mb-2">
                    Citations
                  </h5>
                  <div className="space-y-1">
                    {email.aiDraft.citations.map((citation, idx) => (
                      <div key={idx} className="text-xs text-[#8888a8]">
                        <span className="text-[#F59E0B]">{citation.highlight}</span>:{" "}
                        {citation.text}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
