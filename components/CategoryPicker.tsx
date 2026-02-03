"use client";

import React, { useState, useRef, useEffect } from "react";
import { Tag, Check } from "lucide-react";
import { Category } from "./types";

interface CategoryPickerProps {
  categories: Category[];
  value: string | null;
  onChange: (categoryId: string | null) => void;
}

export default function CategoryPicker({
  categories,
  value,
  onChange,
}: CategoryPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
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

  const selectedCategory = categories.find((cat) => cat.id === value);

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
        title="Change category"
      >
        <Tag size={18} />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-72 bg-[#0c0c1e] border border-[#16163a] rounded-lg shadow-xl z-[9999] max-h-96 overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-2">
            <div className="px-2 py-2 text-xs font-semibold text-[#8888a8] uppercase">
              Select Category
            </div>
            <div className="space-y-1">
              {categories.map((category) => (
                <button
                  key={category.id}
                  onClick={() => {
                    onChange(category.number.toString());
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[#E0E0EE] hover:bg-[#16163a] rounded transition-colors"
                >
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-white shrink-0"
                    style={{ backgroundColor: category.color }}
                  >
                    {category.icon}
                  </div>
                  <div className="flex-1 text-left">
                    <span className="text-[#8888a8] text-xs font-mono mr-2">
                      {category.number > 0 ? `${category.number}.` : ""}
                    </span>
                    <span>{category.label}</span>
                  </div>
                  {value === category.number.toString() && (
                    <Check size={16} className="text-[#3B82F6] shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
