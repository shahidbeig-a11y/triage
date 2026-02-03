"use client";

import { useState, useEffect, useRef } from "react";
import { Calendar, Clock, AlertCircle } from "lucide-react";

interface DayAvailability {
  date: string;
  day_name: string;
  available_hours: number;
  task_capacity: number;
  event_count: number;
  is_weekend: boolean;
}

interface AvailabilitySummary {
  total_events: number;
  days: DayAvailability[];
}

export default function CalendarAvailability() {
  const [availability, setAvailability] = useState<AvailabilitySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [buttonRect, setButtonRect] = useState<DOMRect | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const fetchAvailability = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("http://localhost:8000/api/calendar/availability?days=7");
      if (response.ok) {
        const data = await response.json();
        setAvailability(data.availability);
      } else {
        setError("Failed to fetch calendar availability");
      }
    } catch (err) {
      setError("Error connecting to server");
      console.error("Calendar availability error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      if (!availability) {
        fetchAvailability();
      }
      if (buttonRef.current) {
        setButtonRect(buttonRef.current.getBoundingClientRect());
      }
    }
  }, [isOpen]);

  const getCapacityColor = (capacity: number) => {
    if (capacity >= 15) return "text-green-400";
    if (capacity >= 8) return "text-yellow-400";
    return "text-red-400";
  };

  const getCapacityBg = (capacity: number) => {
    if (capacity >= 15) return "bg-green-500/20 border-green-500/30";
    if (capacity >= 8) return "bg-yellow-500/20 border-yellow-500/30";
    return "bg-red-500/20 border-red-500/30";
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const month = date.toLocaleDateString('en-US', { month: 'short' });
    const day = date.getDate();
    return `${month} ${day}`;
  };

  return (
    <div className="relative">
      {/* Toggle Button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-[#1a1a3e] hover:bg-[#252555] text-white rounded-lg transition-colors border border-[#2d2d5f]"
        title="View calendar availability"
      >
        <Calendar size={16} />
        <span className="text-sm">Availability</span>
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
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar size={18} className="text-blue-400" />
                <h3 className="text-white font-semibold">Calendar Availability</h3>
              </div>
              <button
                onClick={fetchAvailability}
                disabled={loading}
                className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
              >
                {loading ? "Loading..." : "Refresh"}
              </button>
            </div>
            <p className="text-gray-400 text-xs mt-1">
              Task capacity based on your Outlook calendar
            </p>
          </div>

          <div className="max-h-96 overflow-y-auto p-4">
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {loading && !availability && (
              <div className="text-center py-8 text-gray-400">
                <Clock size={32} className="mx-auto mb-2 animate-spin" />
                <p>Loading calendar data...</p>
              </div>
            )}

            {availability && !loading && (
              <div className="space-y-3">
                {/* Summary */}
                <div className="p-3 bg-[#0a0a1e] rounded border border-[#2d2d5f]">
                  <p className="text-xs text-gray-400">
                    Total calendar events: <span className="text-white font-medium">{availability.total_events}</span>
                  </p>
                </div>

                {/* Daily Breakdown */}
                {availability.days.map((day) => (
                  <div
                    key={day.date}
                    className={`p-3 rounded border ${getCapacityBg(day.task_capacity)} ${
                      day.is_weekend ? "opacity-60" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-white font-medium text-sm">
                          {day.day_name}
                        </p>
                        <p className="text-gray-400 text-xs">
                          {formatDate(day.date)}
                        </p>
                      </div>
                      <div className={`text-right ${getCapacityColor(day.task_capacity)}`}>
                        <p className="text-2xl font-bold">{day.task_capacity}</p>
                        <p className="text-xs">tasks</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="flex items-center gap-1 text-gray-400">
                        <Clock size={12} />
                        <span>{day.available_hours}h available</span>
                      </div>
                      <div className="flex items-center gap-1 text-gray-400">
                        <Calendar size={12} />
                        <span>{day.event_count} events</span>
                      </div>
                    </div>

                    {day.is_weekend && (
                      <p className="text-xs text-gray-500 mt-2 italic">Weekend</p>
                    )}
                  </div>
                ))}

                {/* Legend */}
                <div className="pt-3 border-t border-[#2d2d5f]">
                  <p className="text-xs text-gray-400 mb-2">Capacity Levels:</p>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                      <span className="text-gray-400">15+ tasks</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                      <span className="text-gray-400">8-14 tasks</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-red-500"></div>
                      <span className="text-gray-400">&lt;8 tasks</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-[9999]"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
