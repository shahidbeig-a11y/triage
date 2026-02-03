"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";

export default function ReassignButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleReassign = async () => {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch("http://localhost:8000/api/emails/reassign-dates", {
        method: "POST",
      });

      if (response.ok) {
        const data = await response.json();
        setMessage(
          `✓ Reassigned ${data.reassigned} emails! Today: ${data.slots.today}, ` +
          `Tomorrow: ${data.slots.tomorrow}, This Week: ${data.slots.this_week}`
        );
        // Reload page after 2 seconds to show new assignments
        setTimeout(() => window.location.reload(), 2000);
      } else {
        const error = await response.json();
        setMessage(`✗ Error: ${error.detail || "Failed to reassign"}`);
      }
    } catch (error) {
      console.error("Reassign error:", error);
      setMessage("✗ Failed to connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleReassign}
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg transition-colors text-sm font-medium"
        title="Re-run smart assignment with AI durations and calendar availability"
      >
        <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
        <span>{loading ? "Reassigning..." : "Smart Reassign"}</span>
      </button>
      {message && (
        <span className={`text-sm ${message.startsWith("✓") ? "text-green-400" : "text-red-400"}`}>
          {message}
        </span>
      )}
    </div>
  );
}
