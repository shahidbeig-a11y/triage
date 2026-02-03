"use client";

import React, { useState, useRef, useEffect } from "react";
import { Calendar, X, ChevronLeft, ChevronRight } from "lucide-react";

interface CalendarPickerProps {
  value: string | null;
  onChange: (date: string | null) => void;
}

export default function CalendarPicker({ value, onChange }: CalendarPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [viewDate, setViewDate] = useState(new Date());
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const clearDate = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setIsOpen(false);
  };

  const handleDateSelect = (date: Date) => {
    const dateString = date.toISOString().split("T")[0];
    onChange(dateString);
    setIsOpen(false);
  };

  const previousMonth = () => {
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1));
  };

  const nextMonth = () => {
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1));
  };

  // Generate calendar days
  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    const days: (Date | null)[] = [];

    // Add empty cells for days before the first day of the month
    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push(null);
    }

    // Add all days in the month
    for (let day = 1; day <= daysInMonth; day++) {
      days.push(new Date(year, month, day));
    }

    return days;
  };

  const days = getDaysInMonth(viewDate);
  const monthName = viewDate.toLocaleString("default", { month: "long", year: "numeric" });
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const selectedDate = value ? new Date(value + "T00:00:00") : null;

  const isSameDay = (date1: Date | null, date2: Date | null) => {
    if (!date1 || !date2) return false;
    return (
      date1.getFullYear() === date2.getFullYear() &&
      date1.getMonth() === date2.getMonth() &&
      date1.getDate() === date2.getDate()
    );
  };

  // Quick date options
  const getQuickDate = (daysFromNow: number): Date => {
    const date = new Date();
    date.setDate(date.getDate() + daysFromNow);
    return date;
  };

  const quickOptions = [
    { label: "Today", date: getQuickDate(0) },
    { label: "Tomorrow", date: getQuickDate(1) },
    { label: "In 3 days", date: getQuickDate(3) },
    { label: "Next week", date: getQuickDate(7) },
  ];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className={`p-2 rounded hover:bg-[#16163a] transition-colors ${
          value ? "text-[#3B82F6]" : "text-[#8888a8]"
        } hover:text-[#E0E0EE]`}
        title="Set due date"
      >
        <Calendar size={18} />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-80 bg-[#0c0c1e] border border-[#16163a] rounded-lg shadow-xl z-[9999]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-4">
            {/* Header with clear button */}
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold text-[#E0E0EE]">Set Due Date</h4>
              {value && (
                <button
                  onClick={clearDate}
                  className="text-[#8888a8] hover:text-[#E0E0EE] transition-colors"
                  title="Clear date"
                >
                  <X size={16} />
                </button>
              )}
            </div>

            {/* Quick options */}
            <div className="mb-4 grid grid-cols-2 gap-2">
              {quickOptions.map((option) => (
                <button
                  key={option.label}
                  onClick={() => handleDateSelect(option.date)}
                  className="px-3 py-1.5 text-xs text-[#E0E0EE] bg-[#16163a] hover:bg-[#1a1a3a] rounded transition-colors"
                >
                  {option.label}
                </button>
              ))}
            </div>

            {/* Calendar navigation */}
            <div className="flex items-center justify-between mb-3">
              <button
                onClick={previousMonth}
                className="p-1 hover:bg-[#16163a] rounded transition-colors"
              >
                <ChevronLeft size={18} className="text-[#E0E0EE]" />
              </button>
              <span className="text-sm font-semibold text-[#E0E0EE]">{monthName}</span>
              <button
                onClick={nextMonth}
                className="p-1 hover:bg-[#16163a] rounded transition-colors"
              >
                <ChevronRight size={18} className="text-[#E0E0EE]" />
              </button>
            </div>

            {/* Week day headers */}
            <div className="grid grid-cols-7 gap-1 mb-2">
              {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map((day) => (
                <div
                  key={day}
                  className="text-center text-xs font-semibold text-[#8888a8] py-1"
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar days */}
            <div className="grid grid-cols-7 gap-1">
              {days.map((day, index) => {
                if (!day) {
                  return <div key={index} className="aspect-square" />;
                }

                const isToday = isSameDay(day, today);
                const isSelected = isSameDay(day, selectedDate);
                const isPast = day < today;

                return (
                  <button
                    key={index}
                    onClick={() => handleDateSelect(day)}
                    className={`
                      aspect-square flex items-center justify-center text-sm rounded transition-colors
                      ${isSelected ? "bg-[#3B82F6] text-white font-bold" : ""}
                      ${!isSelected && isToday ? "border border-[#3B82F6] text-[#3B82F6]" : ""}
                      ${!isSelected && !isToday && !isPast ? "text-[#E0E0EE] hover:bg-[#16163a]" : ""}
                      ${!isSelected && !isToday && isPast ? "text-[#555577] hover:bg-[#16163a]" : ""}
                    `}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
