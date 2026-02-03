"use client";

import { useState, useEffect, useRef } from "react";

interface UndoAction {
  id: number;
  action_type: string;
  description: string;
  created_at: string;
}

interface UndoResponse {
  actions: UndoAction[];
  total: number;
}

export default function UndoPanel() {
  const [actions, setActions] = useState<UndoAction[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [undoingId, setUndoingId] = useState<number | null>(null);
  const [buttonRect, setButtonRect] = useState<DOMRect | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) {
      fetchActions();
      if (buttonRef.current) {
        setButtonRect(buttonRef.current.getBoundingClientRect());
      }
    }
  }, [isOpen]);

  const fetchActions = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/undo/actions");
      if (response.ok) {
        const data: UndoResponse = await response.json();
        setActions(data.actions);
      }
    } catch (error) {
      console.error("Failed to fetch undo actions:", error);
    }
  };

  const handleUndo = async (actionId: number) => {
    setUndoingId(actionId);
    setIsLoading(true);

    try {
      const response = await fetch(
        `http://localhost:8000/api/undo/actions/${actionId}`,
        {
          method: "POST",
        }
      );

      if (response.ok) {
        const result = await response.json();

        // Show success message
        alert(`Successfully undone: ${result.description || "Action"}`);

        // Refresh the actions list
        await fetchActions();

        // Reload the current page to reflect changes
        window.location.reload();
      } else {
        const error = await response.json();
        alert(`Failed to undo: ${error.detail || "Unknown error"}`);
      }
    } catch (error) {
      console.error("Failed to undo action:", error);
      alert("Failed to undo action");
    } finally {
      setIsLoading(false);
      setUndoingId(null);
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  return (
    <div className="relative">
      {/* Undo Button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-[#1a1a3e] hover:bg-[#252555] text-white rounded-lg transition-colors border border-[#2d2d5f]"
        title="Undo recent actions"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
          />
        </svg>
        <span>Undo</span>
        {actions.length > 0 && (
          <span className="bg-blue-500 text-white text-xs rounded-full px-2 py-0.5">
            {actions.length}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && buttonRect && (
        <div
          className="fixed w-80 max-w-[90vw] bg-[#1a1a3e] border border-[#2d2d5f] rounded-lg shadow-xl z-[10000]"
          style={{
            top: `${buttonRect.bottom + 8}px`,
            right: `${window.innerWidth - buttonRect.right}px`
          }}
        >
          <div className="p-4 border-b border-[#2d2d5f]">
            <h3 className="text-white font-semibold">Recent Actions</h3>
            <p className="text-gray-400 text-sm">
              {actions.length === 0
                ? "No recent actions to undo"
                : "Click to undo an action"}
            </p>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {actions.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                <svg
                  className="w-12 h-12 mx-auto mb-2 opacity-50"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p>No recent actions</p>
              </div>
            ) : (
              actions.map((action) => (
                <div
                  key={action.id}
                  className="p-4 border-b border-[#2d2d5f] hover:bg-[#252555] transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <p className="text-white text-sm font-medium mb-1">
                        {action.description}
                      </p>
                      <p className="text-gray-400 text-xs">
                        {formatTime(action.created_at)}
                      </p>
                    </div>
                    <button
                      onClick={() => handleUndo(action.id)}
                      disabled={isLoading}
                      className={`px-3 py-1 text-sm rounded ${
                        undoingId === action.id
                          ? "bg-gray-600 text-gray-300"
                          : "bg-red-600 hover:bg-red-700 text-white"
                      } transition-colors disabled:opacity-50`}
                    >
                      {undoingId === action.id ? "Undoing..." : "Undo"}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Backdrop to close panel when clicking outside */}
      {isOpen && (
        <div
          className="fixed inset-0 z-[9999]"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
