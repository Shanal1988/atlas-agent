"use client";

import { useParams } from "next/navigation";
import useSWR from "swr";
import { getAnalysis, getOverrides, exportTxtUrl } from "@/lib/api";
import { Analysis, AnalysisOverrides } from "@/lib/types";
import { DecisionBanner } from "@/components/DecisionBanner";
import { CompanyProfileCard } from "@/components/CompanyProfileCard";
import { ScoreGauge } from "@/components/ScoreGauge";
import { RiskBadge } from "@/components/RiskBadge";
import { ValuationTable } from "@/components/ValuationTable";
import { ValuationChart } from "@/components/ValuationChart";
import { RevenueChart } from "@/components/RevenueChart";
import { ROCEROICChart } from "@/components/ROCEROICChart";
import { FisherRadar } from "@/components/FisherRadar";
import { PeerTable } from "@/components/PeerTable";
import { SimilarCompanies } from "@/components/SimilarCompanies";
import { FollowUpChat } from "@/components/FollowUpChat";
import { ThesisDisplay } from "@/components/ThesisDisplay";
import { JudgeFlags } from "@/components/JudgeFlags";
import { BMPScoreTable } from "@/components/BMPScoreTable";
import { FisherScoreTable } from "@/components/FisherScoreTable";
import { FinancialStatementsPanel } from "@/components/FinancialStatements";
import { Download } from "lucide-react";
import { fmtDate } from "@/lib/formatters";

export default function AnalysisPage() {
  const { id } = useParams<{ id: string }>();

  const { data, error, isLoading } = useSWR<Analysis>(
    id ? `analysis/${id}` : null,
    () => getAnalysis(id)
  );

  const { data: overrides = {}, mutate: mutateOverrides } = useSWR<AnalysisOverrides>(
    id ? `overrides/${id}` : null,
    () => getOverrides(id),
    { fallbackData: {} }
  );

  function handleOverridesChange(updated: AnalysisOverrides) {
    mutateOverrides(updated, false);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400">
        Loading analysis...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-64 text-red-400">
        Failed to load analysis.
      </div>
    );
  }

  const { profile, scores, thesis, valuation, industry_analysis, similar_companies, judge_flags } = data;

  // Merge overrides: use override scores if present, else original
  const bmp = overrides.bmp
    ? { ...scores.bmp, score: overrides.bmp.score, verdict: overrides.bmp.verdict, answers: overrides.bmp.answers as any }
    : scores.bmp;
  const fisher = overrides.fisher
    ? { ...scores.fisher, total: overrides.fisher.total, rating: overrides.fisher.rating, points: overrides.fisher.points as any }
    : scores.fisher;

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {data.company}
            <span className="ml-2 text-blue-400 font-mono text-lg">({data.ticker})</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {fmtDate(data.date)} · {data.analyst}
          </p>
        </div>
        <a
          href={exportTxtUrl(id)}
          download
          className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white text-sm px-3 py-2 rounded-lg transition-colors"
        >
          <Download className="w-4 h-4" />
          Download Thesis
        </a>
      </div>

      <DecisionBanner
        decision={thesis.decision}
        rationale={thesis.decision_rationale}
        company={data.company}
        ticker={data.ticker}
      />

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Left column - 2/3 */}
        <div className="lg:col-span-2 space-y-4">
          <CompanyProfileCard profile={profile} />
          <ThesisDisplay thesis={thesis} />
          {judge_flags && Object.keys(judge_flags).length > 0 && (
            <JudgeFlags flags={judge_flags} />
          )}
        </div>

        {/* Right column - 1/3 */}
        <div className="space-y-4">
          {/* Scores */}
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-4">
              Scores
            </h3>
            <div className="flex flex-wrap justify-around gap-4">
              <ScoreGauge
                label="BMP"
                score={bmp.score}
                max={5}
                verdict={bmp.verdict}
              />
              <ScoreGauge
                label="Fisher"
                score={fisher.total}
                max={15}
                verdict={fisher.rating.split(" — ")[0]}
              />
              <ScoreGauge
                label="Selection"
                score={scores.selection.score}
                max={8}
                verdict={scores.selection.verdict}
              />
            </div>
          </div>

          <RiskBadge risk={scores.risk} />

          <ValuationTable valuation={valuation!} shares={profile.market_cap / profile.current_price} />
        </div>
      </div>

      {/* Full-width sections */}
      <div className="space-y-6">
        {valuation?.available && <ValuationChart valuation={valuation} />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {profile.revenues?.length > 0 && (
            <RevenueChart revenues={profile.revenues} cagr={profile.revenue_cagr} />
          )}
          <ROCEROICChart profile={profile} />
        </div>

        <FisherRadar fisher={fisher} />

        {/* Editable score tables */}
        <BMPScoreTable
          analysisId={id}
          bmp={scores.bmp}
          overrides={overrides}
          onOverridesChange={handleOverridesChange}
        />

        <FisherScoreTable
          analysisId={id}
          fisher={scores.fisher}
          overrides={overrides}
          onOverridesChange={handleOverridesChange}
        />

        {/* Financial Statements */}
        <FinancialStatementsPanel analysisId={id} />

        {industry_analysis && <PeerTable industry={industry_analysis} />}
        {similar_companies?.length ? <SimilarCompanies companies={similar_companies} /> : null}

        <FollowUpChat
          analysisId={id}
          company={data.company}
          ticker={data.ticker}
          overrides={overrides}
          onOverridesChange={handleOverridesChange}
        />
      </div>
    </div>
  );
}
