"use client";

import React from "react";

interface UrgencyBarProps {
  score: number;
  staleDays: number;
  floorOverride: boolean;
}

export default function UrgencyBar({ score, staleDays, floorOverride }: UrgencyBarProps) {
  // Determine color based on score
  const getColor = (score: number): string => {
    if (score >= 90) return "#D94F4F"; // red
    if (score >= 70) return "#D4793A"; // orange
    if (score >= 40) return "#F59E0B"; // amber
    return "#55557a"; // muted gray
  };

  const color = getColor(score);
  const fillPercentage = Math.min(100, Math.max(0, score));

  // Collect badges to display
  const badges = [];
  if (score >= 90) {
    badges.push(
      <span
        key="critical"
        className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-[#D94F4F] text-white rounded whitespace-nowrap"
      >
        Critical
      </span>
    );
  }
  if (staleDays > 0) {
    badges.push(
      <span
        key="stale"
        className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-[#F59E0B] text-[#0c0c1e] rounded whitespace-nowrap"
      >
        Stale
      </span>
    );
  }
  if (floorOverride) {
    badges.push(
      <span
        key="floor"
        className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-[#F59E0B] text-[#0c0c1e] rounded whitespace-nowrap"
      >
        ⚠ Floor
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      {/* Row 1: Urgency bar aligned with Badge 1 */}
      <div className="flex items-center gap-3">
        {/* Urgency bar */}
        <div className="relative w-32 h-2 bg-[#16163a] rounded-full overflow-hidden border border-[#2a2a4a]">
          <div
            className="absolute top-0 left-0 h-full rounded-full transition-all duration-300"
            style={{
              width: `${fillPercentage}%`,
              backgroundColor: color,
            }}
          />
        </div>
        {/* Badge 1 */}
        {badges[0]}
      </div>

      {/* Row 2: Urgency score label aligned with Badge 2 */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-[#8888a8] w-32">
          Urgency: <span className="text-[#E0E0EE] font-medium">{score}</span>
        </span>
        {/* Badge 2 */}
        {badges[1]}
      </div>

      {/* Row 3: Badge 3 (if exists) */}
      {badges[2] && (
        <div className="flex items-center gap-3">
          <div className="w-32" />
          {badges[2]}
        </div>
      )}
    </div>
  );
}
