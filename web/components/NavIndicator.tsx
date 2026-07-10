"use client";

import Link from "next/link";
import { useAnalysisContext } from "@/contexts/AnalysisContext";

export function NavIndicator() {
  const { activeJob } = useAnalysisContext();
  if (!activeJob) return null;

  return (
    <Link
      href={`/running/${activeJob.jobId}`}
      className="ml-auto flex items-center gap-2 bg-blue-900/40 border border-blue-700 text-blue-300 text-xs px-3 py-1.5 rounded-full hover:bg-blue-900/70 transition-colors"
    >
      <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse shrink-0" />
      {activeJob.company} — Running
    </Link>
  );
}
