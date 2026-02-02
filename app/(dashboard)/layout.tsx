"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const tabs = [
    { name: "Work", href: "/work", count: 13, color: "bg-green-600" },
    { name: "Other", href: "/other", count: 10, color: "bg-blue-600" },
    { name: "Ad-Hoc", href: "/adhoc", count: 4, color: "bg-amber-600" },
    { name: "Admin", href: "/admin", count: 8, color: "bg-gray-600" },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-[#08081a] text-[#E0E0EE]">
      {/* Header */}
      <header className="border-b border-[#1a1a3a] bg-[#0a0a1e]">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">TRIAGE</h1>
              <span className="rounded bg-gray-700 px-2 py-0.5 text-[10px] font-medium text-gray-300">
                v4.2
              </span>
            </div>
            <div className="text-sm text-gray-500">20/day limit</div>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="border-b border-[#1a1a3a] bg-[#0a0a1e]">
        <div className="container mx-auto px-6">
          <div className="flex gap-1">
            {tabs.map((tab) => {
              const isActive = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-[#16163a] text-white"
                      : "bg-transparent text-[#55557a] hover:text-white"
                  }`}
                >
                  <span>{tab.name}</span>
                  <span
                    className={`${tab.color} rounded-full px-2 py-0.5 text-xs font-semibold text-white`}
                  >
                    {tab.count}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Page Content */}
      <main className="container mx-auto flex-1 px-6 py-8">{children}</main>

      {/* Footer */}
      <footer className="border-t border-[#1a1a3a] bg-[#0a0a1e] py-3">
        <div className="container mx-auto px-6">
          <p className="text-center text-xs text-gray-600">
            v4.2 · Work → Other → Ad-Hoc → Admin
          </p>
        </div>
      </footer>
    </div>
  );
}
