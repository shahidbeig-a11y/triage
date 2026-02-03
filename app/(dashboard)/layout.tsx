"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, ChevronRight, Calendar } from "lucide-react";
import UndoPanel from "@/components/UndoPanel";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [newMailExpanded, setNewMailExpanded] = useState(true);
  const [allMailExpanded, setAllMailExpanded] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());

  // Update date every minute
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentDate(new Date());
    }, 60000);
    return () => clearInterval(timer);
  }, []);

  // Format date display
  const formatDate = () => {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    const dayName = days[currentDate.getDay()];
    const monthName = months[currentDate.getMonth()];
    const date = currentDate.getDate();
    const year = currentDate.getFullYear();

    return `${dayName}, ${monthName} ${date}, ${year}`;
  };

  return (
    <div className="flex min-h-screen bg-[#08081a] text-[#E0E0EE] overflow-x-hidden">
      {/* Floating Sidebar */}
      <aside className="fixed left-0 top-0 h-screen w-64 border-r border-[#1a1a3a] bg-[#0a0a1e] flex flex-col shrink-0 z-50">
        {/* Header */}
        <div className="p-4 border-b border-[#1a1a3a]">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">TRIAGE</h1>
            <span className="rounded bg-gray-700 px-2 py-0.5 text-[10px] font-medium text-gray-300">
              v4.3
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {/* New Mail Section */}
          <div>
            <button
              onClick={() => setNewMailExpanded(!newMailExpanded)}
              className="flex items-center justify-between w-full px-3 py-2 rounded text-sm font-semibold text-[#E0E0EE] hover:bg-[#16163a]/50 transition-colors"
            >
              <span>New Mail</span>
              {newMailExpanded ? (
                <ChevronDown size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
            </button>
            {newMailExpanded && (
              <div className="ml-4 mt-1 space-y-1">
                <Link
                  href="/new-mail/work"
                  className={`block px-3 py-2 rounded text-sm transition-colors ${
                    pathname === "/new-mail/work"
                      ? "bg-[#16163a] text-white font-medium"
                      : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
                  }`}
                >
                  Work
                </Link>
                <Link
                  href="/new-mail/other"
                  className={`block px-3 py-2 rounded text-sm transition-colors ${
                    pathname === "/new-mail/other"
                      ? "bg-[#16163a] text-white font-medium"
                      : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
                  }`}
                >
                  Other
                </Link>
              </div>
            )}
          </div>

          {/* All Mail Section */}
          <div>
            <button
              onClick={() => setAllMailExpanded(!allMailExpanded)}
              className="flex items-center justify-between w-full px-3 py-2 rounded text-sm font-semibold text-[#E0E0EE] hover:bg-[#16163a]/50 transition-colors"
            >
              <span>All Mail</span>
              {allMailExpanded ? (
                <ChevronDown size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
            </button>
            {allMailExpanded && (
              <div className="ml-4 mt-1 space-y-1">
                <Link
                  href="/all-mail/work"
                  className={`block px-3 py-2 rounded text-sm transition-colors ${
                    pathname === "/all-mail/work"
                      ? "bg-[#16163a] text-white font-medium"
                      : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
                  }`}
                >
                  Work
                </Link>
                <Link
                  href="/all-mail/other"
                  className={`block px-3 py-2 rounded text-sm transition-colors ${
                    pathname === "/all-mail/other"
                      ? "bg-[#16163a] text-white font-medium"
                      : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
                  }`}
                >
                  Other
                </Link>
                <Link
                  href="/all-mail/unclassified"
                  className={`block px-3 py-2 rounded text-sm transition-colors ${
                    pathname === "/all-mail/unclassified"
                      ? "bg-[#16163a] text-white font-medium"
                      : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
                  }`}
                >
                  Unclassified
                </Link>
              </div>
            )}
          </div>

          {/* Divider */}
          <div className="h-px bg-[#1a1a3a] my-4" />

          {/* Ad-hoc */}
          <Link
            href="/adhoc"
            className={`block px-3 py-2 rounded text-sm font-medium transition-colors ${
              pathname === "/adhoc"
                ? "bg-[#16163a] text-white"
                : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
            }`}
          >
            Ad-hoc
          </Link>

          {/* Admin */}
          <Link
            href="/admin"
            className={`block px-3 py-2 rounded text-sm font-medium transition-colors ${
              pathname === "/admin"
                ? "bg-[#16163a] text-white"
                : "text-[#8888a8] hover:bg-[#16163a]/50 hover:text-white"
            }`}
          >
            Admin
          </Link>
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-[#1a1a3a]">
          <p className="text-xs text-gray-600 text-center">
            New Mail → Process → All Mail
          </p>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 ml-64">
        {/* Date Header */}
        <div className="border-b border-[#1a1a3a] bg-[#0a0a1e] px-8 py-4 overflow-x-hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[#8888a8]">
              <Calendar size={16} />
              <span className="text-sm font-medium">{formatDate()}</span>
            </div>
            <div className="flex items-center gap-3">
              <UndoPanel />
            </div>
          </div>
        </div>

        <main className="flex-1 p-8 overflow-y-auto overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
}
