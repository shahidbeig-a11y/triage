export default function AdminPage() {
  const sections = [
    "Task Limit Per Day",
    "Urgency Floor",
    "System Categories",
    "Custom Categories",
  ];

  return (
    <div className="space-y-4">
      {sections.map((section) => (
        <div
          key={section}
          className="rounded-lg border border-[#1a1a3a] bg-[#0a0a1e] p-6"
        >
          <h3 className="text-lg font-semibold text-white">{section}</h3>
          <p className="mt-2 text-sm text-gray-500">
            Settings will appear here
          </p>
        </div>
      ))}
    </div>
  );
}
