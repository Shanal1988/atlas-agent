// TypeScript interfaces matching the Atlas thesis JSON output schema

export interface RevenueYear {
  year: string;
  revenue: number;
}

export interface CompanyProfile {
  name: string;
  ticker: string;
  exchange: string;
  sector: string;
  industry: string;
  market_cap: number;
  current_price: number;
  pe_ratio: number | null;
  beta: number | null;
  revenue_cagr: number | null;
  revenues: RevenueYear[];
  free_cash_flow: number | null;
  operating_cash_flow: number | null;
  operating_income: number | null;
  roe: number | null;
  roce_avg: number | null;
  roic_avg: number | null;
  roce_trend: string | null;
  roic_trend: string | null;
  insider_ownership_pct: number | null;
  description: string;
  moat: string;
  growth_drivers: string[];
  risk_factors: string[];
  news?: string[];
}

export interface BMPAnswer {
  label: string;
  rating: "YES" | "PARTIAL" | "NO";
  reasoning: string;
}

export interface BMPScore {
  score: number;
  verdict: string;
  answers: BMPAnswer[];
}

export interface FisherPoint {
  key: string;
  label: string;
  score: number;
  reasoning: string;
}

export interface FisherScore {
  total: number;
  rating: string;
  points: FisherPoint[];
  evidence?: string;
}

export interface SelectionAnswer {
  key: string;
  label: string;
  rating: "YES" | "PARTIAL" | "NO";
  reasoning: string;
}

export interface SelectionScore {
  score: number;
  verdict: string;
  answers: SelectionAnswer[];
}

export interface RiskFactor {
  key: string;
  label: string;
  penalty: number;
  reasoning: string;
}

export interface RiskScore {
  category: "Diamond" | "Gold" | "Silver" | "Bronze" | "Glass" | "Egg";
  alloc_label: string;
  conviction: "HIGH" | "MEDIUM" | "LOW";
  position_pct: number;
  base_nos: number;
  total_penalty: number;
  adjusted_nos: number;
  factors: RiskFactor[];
  summary: string;
  penalty_floors: string[];
}

export interface Scores {
  bmp: BMPScore;
  fisher: FisherScore;
  selection: SelectionScore;
  risk: RiskScore;
}

export interface JudgeFlag {
  passed: boolean;
  severity: "INFO" | "WARN" | "FAIL";
  flags: string[];
}

export interface DhandhoPhaseRow {
  year: number;
  fcf: number;
  pv: number;
}

export interface DhandhoResult {
  rows: DhandhoPhaseRow[];
  pv_sum: number;
  pv_tv: number;
  net_cash: number;
  iv: number;
}

export interface GrahamResult {
  lower: number;
  higher: number;
  lo_rate: number;
  hi_rate: number;
  avg_5yr_ni_mn: number;
}

export interface DCFResult {
  rows: DhandhoPhaseRow[];
  pv_sum: number;
  pv_tv: number;
  net_cash: number;
  iv: number;
}

export interface ExpReturnsResult {
  iv: number;
  ni_cagr_pct: number;
  projected_ni: number;
  exit_pe: number;
  projected_cap: number;
}

export interface ValuationResult {
  available: boolean;
  base_mn: number;
  base_label: string;
  is_financial: boolean;
  is_capex_heavy: boolean;
  fcf_mn: number | null;
  ocf_mn: number | null;
  op_income_mn: number | null;
  nopat_mn: number | null;
  net_cash_mn: number | null;
  shares: number;
  mktcap_mn: number;
  dhandho: { lower: DhandhoResult; higher: DhandhoResult };
  graham: GrahamResult | null;
  dcf: DCFResult | null;
  exp_returns: ExpReturnsResult | null;
  phases_lower: [number, number, number][];
  phases_higher: [number, number, number][];
}

export interface PeerMetric {
  ticker: string;
  name: string;
  market_cap: number | null;
  pe_ratio: number | null;
  roe: number | null;
  roic: number | null;
  operating_margin: number | null;
  revenue_growth: number | null;
  price: number | null;
  sector: string | null;
  industry: string | null;
}

export interface IndustrySections {
  INDUSTRY_OVERVIEW?: string;
  MARKET_STRUCTURE?: string;
  COMPETITIVE_POSITION?: string;
  KEY_DYNAMICS?: string;
  PEER_COMPARISON?: string;
  MOAT_VS_PEERS?: string;
}

export interface IndustryResult {
  peers: PeerMetric[];
  sections: IndustrySections;
  peer_tickers: string[];
}

export interface SimilarCompany {
  ticker: string;
  name: string;
  market_cap: number | null;
  price: number | null;
  sector: string | null;
  industry: string | null;
  pe_ratio: number | null;
  roe: number | null;
  roic: number | null;
  revenue_growth: number | null;
  operating_margin: number | null;
  fcf_yield: number | null;
  multibagger_score: number;
}

export interface ThesisSections {
  executive_summary: string;
  bull_case: string[];
  bear_case: string[];
  thesis_statement: string;
  destination: string;
  watch_points: string[];
  decision: "INVEST" | "WATCHLIST" | "PASS";
  decision_rationale: string;
}

export interface Analysis {
  company: string;
  ticker: string;
  date: string;
  analyst: string;
  profile: CompanyProfile;
  scores: Scores;
  judge_flags: Record<string, JudgeFlag>;
  valuation: ValuationResult | null;
  industry_analysis: IndustryResult | null;
  similar_companies: SimilarCompany[] | null;
  thesis: ThesisSections;
  formatted_thesis: string;
}

export interface AnalysisSummary {
  id: string;
  file: string;
  company: string;
  ticker: string;
  date: string;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  current_price: number | null;
  decision: "INVEST" | "WATCHLIST" | "PASS" | null;
  decision_rationale: string | null;
  bmp_score: number | null;
  fisher_score: number | null;
  selection_score: number | null;
  risk_category: string | null;
  position_pct: number | null;
  conviction: string | null;
  revenue_cagr: number | null;
  roe: number | null;
  moat: string | null;
}

// SSE event types
export type ProgressEvent =
  | { type: "snapshot"; status: string; current_stage?: string; completed_stages?: string[]; logs?: any[]; ticker?: string; result_json_path?: string; error?: string }
  | { type: "stage_start"; stage: string; timestamp: number }
  | { type: "stage_complete"; stage: string; timestamp: number }
  | { type: "log"; line: string; stage: string; timestamp: number }
  | { type: "done"; json_path: string; txt_path?: string; ticker?: string; timestamp: number }
  | { type: "error"; error: string; stage?: string };

export interface Stage {
  key: string;
  label: string;
  order: number;
}
