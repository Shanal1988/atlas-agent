"use client";

import { useState, useRef, DragEvent } from "react";
import { Upload, X, Loader2 } from "lucide-react";
import { uploadFinancialFile } from "@/lib/api";

interface Props {
  analysisId: string;
  onSuccess: (data: object) => void;
  onClose: () => void;
}

export function FileUploadDialog({ analysisId, onSuccess, onClose }: Props) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    const allowed = [".xlsx", ".xls", ".csv", ".pdf"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowed.includes(ext)) {
      setError("Unsupported file type. Use .xlsx, .csv, or .pdf");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await uploadFinancialFile(analysisId, file);
      onSuccess(data);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Upload Financial File</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            dragging ? "border-blue-500 bg-blue-950/30" : "border-slate-600 hover:border-slate-500"
          }`}
        >
          {loading ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              <p className="text-slate-400 text-sm">Parsing file with AI...</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-8 h-8 text-slate-400" />
              <p className="text-slate-300 text-sm font-medium">Drop file here or click to browse</p>
              <p className="text-slate-500 text-xs">.xlsx, .csv, .pdf supported</p>
            </div>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv,.pdf"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />

        {error && <p className="mt-3 text-red-400 text-sm">{error}</p>}

        <p className="mt-3 text-slate-500 text-xs">
          Atlas AI will extract financial data from your file and merge it into the statements table.
        </p>
      </div>
    </div>
  );
}
