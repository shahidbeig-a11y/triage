"use client";

import { useState } from "react";
import { FolderOpen, Sparkles, Check, X } from "lucide-react";

interface FolderRecommendation {
  email_id: number;
  subject: string;
  from_name: string;
  recommended_folder: string;
  is_new_folder: boolean;
  confidence: number;
  reasoning: string;
  alternative_folder: string | null;
}

export default function FyiFolderOrganizer() {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<FolderRecommendation[]>([]);
  const [approving, setApproving] = useState(false);
  const [message, setMessage] = useState("");

  const fetchRecommendations = async () => {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch("http://localhost:8000/api/folders/recommend-fyi-group", {
        method: "POST",
      });

      if (response.ok) {
        const data = await response.json();
        setRecommendations(data.recommendations || []);

        if (data.recommendations.length === 0) {
          setMessage("No FYI - Group emails to organize");
        }
      } else {
        setMessage("Failed to fetch recommendations");
      }
    } catch (error) {
      console.error("Fetch error:", error);
      setMessage("Error connecting to server");
    } finally {
      setLoading(false);
    }
  };

  const approveAll = async () => {
    setApproving(true);
    setMessage("");

    try {
      const response = await fetch("http://localhost:8000/api/folders/approve-fyi-folders", {
        method: "POST",
      });

      if (response.ok) {
        const data = await response.json();
        setMessage(`✓ Approved ${data.approved} emails for filing!`);
        setRecommendations([]);

        // Reload page after 2 seconds
        setTimeout(() => window.location.reload(), 2000);
      } else {
        setMessage("Failed to approve folder assignments");
      }
    } catch (error) {
      console.error("Approve error:", error);
      setMessage("Error connecting to server");
    } finally {
      setApproving(false);
    }
  };

  const handleOpen = () => {
    setIsOpen(true);
    if (recommendations.length === 0) {
      fetchRecommendations();
    }
  };

  return (
    <div className="relative">
      {/* Toggle Button */}
      <button
        onClick={handleOpen}
        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors text-sm font-medium"
        title="Organize FYI - Group emails into folders"
      >
        <Sparkles size={16} />
        <span>Organize FYI</span>
      </button>

      {/* Modal */}
      {isOpen && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-[9998]"
            onClick={() => setIsOpen(false)}
          />

          <div className="fixed inset-0 flex items-center justify-center z-[9999] p-4">
            <div className="bg-[#1a1a3e] border border-[#2d2d5f] rounded-lg shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
              {/* Header */}
              <div className="p-6 border-b border-[#2d2d5f]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FolderOpen size={24} className="text-purple-400" />
                    <div>
                      <h2 className="text-xl font-bold text-white">FYI - Group Organizer</h2>
                      <p className="text-sm text-gray-400">
                        AI-powered folder recommendations for informational emails
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setIsOpen(false)}
                    className="text-gray-400 hover:text-white"
                  >
                    <X size={24} />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-6">
                {loading && (
                  <div className="text-center py-12">
                    <Sparkles size={48} className="mx-auto mb-4 text-purple-400 animate-pulse" />
                    <p className="text-gray-400">Analyzing emails and recommending folders...</p>
                  </div>
                )}

                {!loading && recommendations.length === 0 && !message && (
                  <div className="text-center py-12 text-gray-400">
                    <p>Click "Get Recommendations" to organize FYI - Group emails</p>
                  </div>
                )}

                {message && (
                  <div className={`text-center py-4 px-4 rounded ${
                    message.startsWith("✓") ? "bg-green-500/10 text-green-400" : "bg-gray-700 text-gray-300"
                  }`}>
                    {message}
                  </div>
                )}

                {!loading && recommendations.length > 0 && (
                  <div className="space-y-3">
                    {recommendations.map((rec) => (
                      <div
                        key={rec.email_id}
                        className="bg-[#0a0a1e] border border-[#2d2d5f] rounded-lg p-4"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                              <FolderOpen size={16} className="text-purple-400 shrink-0" />
                              <span className="text-white font-medium truncate">
                                {rec.recommended_folder}
                              </span>
                              {rec.is_new_folder && (
                                <span className="text-xs bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded">
                                  NEW
                                </span>
                              )}
                              <span className="text-xs text-gray-500">
                                {Math.round(rec.confidence * 100)}% confident
                              </span>
                            </div>

                            <p className="text-sm text-gray-300 mb-1 truncate">
                              <span className="text-gray-500">From:</span> {rec.from_name}
                            </p>
                            <p className="text-sm text-gray-300 mb-2 truncate">
                              <span className="text-gray-500">Subject:</span> {rec.subject}
                            </p>

                            <p className="text-xs text-gray-400 italic">
                              {rec.reasoning}
                            </p>

                            {rec.alternative_folder && (
                              <p className="text-xs text-gray-500 mt-2">
                                Alternative: {rec.alternative_folder}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="p-6 border-t border-[#2d2d5f] flex items-center justify-between">
                <div className="text-sm text-gray-400">
                  {recommendations.length > 0 && `${recommendations.length} emails ready to organize`}
                </div>

                <div className="flex items-center gap-3">
                  {recommendations.length === 0 && !loading && (
                    <button
                      onClick={fetchRecommendations}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors text-sm font-medium"
                    >
                      Get Recommendations
                    </button>
                  )}

                  {recommendations.length > 0 && (
                    <>
                      <button
                        onClick={fetchRecommendations}
                        disabled={loading}
                        className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors text-sm"
                      >
                        Refresh
                      </button>
                      <button
                        onClick={approveAll}
                        disabled={approving}
                        className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white rounded-lg transition-colors text-sm font-medium"
                      >
                        <Check size={16} />
                        <span>{approving ? "Approving..." : "Approve All"}</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
