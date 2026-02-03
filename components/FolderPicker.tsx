"use client";

import React, { useState, useRef, useEffect } from "react";
import { FolderOpen, Check, Plus, Search } from "lucide-react";
import { Folder } from "./types";

interface FolderPickerProps {
  folders: Folder[];
  value: string | null;
  onChange: (folder: string | null) => void;
  onCreateFolder: (name: string) => void;
}

export default function FolderPicker({
  folders,
  value,
  onChange,
  onCreateFolder,
}: FolderPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setIsCreating(false);
        setNewFolderName("");
        setSearchQuery("");
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  // Filter folders based on search query
  const filteredFolders = folders.filter((folder) =>
    folder.name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      onCreateFolder(newFolderName.trim());
      setNewFolderName("");
      setIsCreating(false);
      setIsOpen(false);
    }
  };

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
        title="Move to folder"
      >
        <FolderOpen size={18} />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-64 bg-[#0c0c1e] border border-[#16163a] rounded-lg shadow-xl z-[9999]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-2">
            <div className="px-2 py-2 text-xs font-semibold text-[#8888a8] uppercase">
              Move to Folder
            </div>

            {/* Search bar */}
            <div className="relative mb-2">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8888a8]"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search folders..."
                className="w-full pl-8 pr-3 py-2 bg-[#16163a] border border-[#16163a] rounded text-[#E0E0EE] text-sm placeholder:text-[#8888a8] focus:outline-none focus:ring-2 focus:ring-[#3B82F6]"
              />
            </div>

            {/* Folder list */}
            <div className="space-y-1 mb-2 max-h-64 overflow-y-auto">
              {filteredFolders.length > 0 ? (
                filteredFolders.map((folder) => (
                <button
                  key={folder.id}
                  onClick={() => {
                    onChange(folder.name);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center gap-3 px-3 py-2 text-sm text-[#E0E0EE] hover:bg-[#16163a] rounded transition-colors"
                >
                  <FolderOpen size={16} className="text-[#8888a8] shrink-0" />
                  <span className="flex-1 text-left capitalize">{folder.name}</span>
                  {value === folder.name && (
                    <Check size={16} className="text-[#3B82F6] shrink-0" />
                  )}
                </button>
              ))
              ) : (
                <div className="px-3 py-4 text-center text-sm text-[#8888a8]">
                  No folders found
                </div>
              )}
            </div>

            {/* Create new folder */}
            {!isCreating ? (
              <button
                onClick={() => setIsCreating(true)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[#3B82F6] hover:bg-[#16163a] rounded transition-colors"
              >
                <Plus size={16} />
                <span>Create new folder</span>
              </button>
            ) : (
              <div className="p-2 bg-[#16163a] rounded">
                <input
                  type="text"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleCreateFolder();
                    } else if (e.key === "Escape") {
                      setIsCreating(false);
                      setNewFolderName("");
                    }
                  }}
                  placeholder="Folder name..."
                  autoFocus
                  className="w-full px-2 py-1 bg-[#0c0c1e] border border-[#16163a] rounded text-[#E0E0EE] text-sm focus:outline-none focus:ring-2 focus:ring-[#3B82F6]"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={handleCreateFolder}
                    className="flex-1 px-2 py-1 text-xs bg-[#3B82F6] text-white rounded hover:bg-[#2563EB] transition-colors"
                  >
                    Create
                  </button>
                  <button
                    onClick={() => {
                      setIsCreating(false);
                      setNewFolderName("");
                    }}
                    className="flex-1 px-2 py-1 text-xs bg-[#0c0c1e] text-[#8888a8] rounded hover:bg-[#16163a] transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
