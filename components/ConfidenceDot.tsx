"use client";

import React from "react";

interface ConfidenceDotProps {
  confidence: number;
}

export default function ConfidenceDot({ confidence }: ConfidenceDotProps) {
  // Determine color based on confidence
  const getColor = (confidence: number): string => {
    if (confidence >= 0.9) return "#10B981"; // green
    if (confidence >= 0.75) return "#3B82F6"; // blue
    return "#F59E0B"; // amber
  };

  const color = getColor(confidence);
  const displayValue = (confidence * 100).toFixed(0);

  return (
    <div className="relative group">
      {/* Colored dot */}
      <div
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: color }}
      />

      {/* Tooltip */}
      <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 px-2 py-1 bg-[#16163a] text-[#E0E0EE] text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
        {confidence.toFixed(2)} confidence
        <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-[#16163a]" />
      </div>
    </div>
  );
}
