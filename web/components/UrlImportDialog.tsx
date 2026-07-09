"use client";

import { useState } from "react";
import { Link, X, Loader2 } from "lucide-react";
import { importFromUrl } from "@/lib/api";

interface Props {
  analysisId: string;
  onSuccess: (data: object) => void;
  onClose: () => void;
}

export function UrlImportDialog({ analysisId, onSuccess, onClose }: Props) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExtract() {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await importFromUrl(analysisId, url.trim());
      onSuccess(data);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Import from URL</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-slate-400 text-sm mb-3">
          Paste a URL to an SEC filing, investor relations page, or any page with financial data.
        </p>

        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleExtract()}
            placeholder="https://..."
            disabled={loading}
            className="flex-1 bg-slate-700 text-white text-sm rounded-lg px-3 py-2 placeholder-slate-500 outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            onClick={handleExtract}
            disabled={loading || !url.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link className="w-4 h-4" />}
            {loading ? "Extracting..." : "Extract"}
          </button>
        </div>

        {error && <p className="mt-3 text-red-400 text-sm">{error}</p>}

        <p className="mt-3 text-slate-500 text-xs">
          Atlas AI fetches the page content and extracts financial figures automatically.
        </p>
      </div>
    </div>
  );
}
