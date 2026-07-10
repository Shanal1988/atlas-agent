"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface ActiveJob {
  jobId: string;
  company: string;
}

interface AnalysisContextType {
  activeJob: ActiveJob | null;
  setActiveJob: (job: ActiveJob | null) => void;
}

const AnalysisContext = createContext<AnalysisContextType>({
  activeJob: null,
  setActiveJob: () => {},
});

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [activeJob, setActiveJobState] = useState<ActiveJob | null>(null);

  // Restore from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("atlas_active_job");
      if (stored) setActiveJobState(JSON.parse(stored));
    } catch {}
  }, []);

  function setActiveJob(job: ActiveJob | null) {
    setActiveJobState(job);
    if (job) {
      localStorage.setItem("atlas_active_job", JSON.stringify(job));
    } else {
      localStorage.removeItem("atlas_active_job");
    }
  }

  return (
    <AnalysisContext.Provider value={{ activeJob, setActiveJob }}>
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysisContext() {
  return useContext(AnalysisContext);
}
