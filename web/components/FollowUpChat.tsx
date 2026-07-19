"use client";

import { useState, useRef, useEffect } from "react";
import { askFollowUp, saveOverrides, getChatHistory, patchChatMessage } from "@/lib/api";
import { Send, Loader2, Globe, Check, X, Paperclip } from "lucide-react";
import {
  ChatSource,
  ProposedUpdate,
  AnalysisOverrides,
  BMPScore,
  FisherScore,
  BMPAnswerOverride,
  FisherPointOverride,
} from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  proposed_updates?: ProposedUpdate[];
  updatesApplied?: boolean;
}

const STARTER_QUESTIONS = [
  "What are the main risks?",
  "What's the bull case?",
  "What price would make this a buy?",
];

interface Props {
  analysisId: string;
  company: string;
  ticker: string;
  bmp: BMPScore;
  fisher: FisherScore;
  overrides: AnalysisOverrides;
  onOverridesChange: (updated: AnalysisOverrides) => void;
}

export function FollowUpChat({ analysisId, company, ticker, bmp, fisher, overrides, onOverridesChange }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Restore persisted chat history on mount (survives page refreshes)
  useEffect(() => {
    let cancelled = false;
    getChatHistory(analysisId)
      .then((data) => {
        if (cancelled) return;
        setMessages(
          data.messages.map((m) => ({
            role: m.role,
            content: m.attachment ? `${m.content}\n📎 ${m.attachment}` : m.content,
            sources: m.sources ?? undefined,
            proposed_updates: m.proposed_updates ?? undefined,
            updatesApplied: m.updates_applied,
          }))
        );
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setHistoryLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [analysisId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const fileToSend = attachedFile;
    setInput("");
    setAttachedFile(null);
    setError(null);
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: fileToSend ? `${trimmed}\n📎 ${fileToSend.name}` : trimmed,
      },
    ]);
    setLoading(true);

    try {
      const data = await askFollowUp(analysisId, trimmed, fileToSend ?? undefined);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          proposed_updates: data.proposed_updates,
        },
      ]);
    } catch (e) {
      // Remove the optimistic user message so local indices stay in sync
      // with the server-side history (the failed turn was never persisted).
      setMessages((prev) => prev.slice(0, -1));
      setInput(trimmed);
      setError(e instanceof Error ? e.message : "Failed to get response");
    } finally {
      setLoading(false);
    }
  }

  // Thesis fields that are string arrays — chat sends new_value as a single
  // string, so split it into list items before storing.
  const ARRAY_FIELDS = new Set([
    "bull_case", "bear_case", "watch_points",
    "short_term_catalysts", "short_term_risks", "medium_term_milestones",
  ]);

  const THESIS_KEYS = new Set([
    "executive_summary", "bull_case", "bear_case", "thesis_statement",
    "destination", "watch_points", "decision", "decision_rationale",
    "short_term_outlook", "short_term_catalysts", "short_term_risks",
    "medium_term_outlook", "medium_term_milestones",
  ]);

  const BMP_RATING_SCORE: Record<string, number> = { YES: 1, PARTIAL: 0.5, NO: 0 };

  function bmpVerdict(score: number): string {
    if (score >= 4) return "STRONG PASS";
    if (score >= 3) return "PASS";
    if (score >= 2) return "BORDERLINE";
    return "FAIL";
  }

  function fisherRating(total: number): string {
    if (total >= 12) return "EXCELLENT";
    if (total >= 9) return "GOOD";
    if (total >= 6) return "FAIR";
    return "POOR";
  }

  function toListItems(value: string): string[] {
    const lines = value
      .split("\n")
      .map((l) => l.replace(/^\s*(?:[-*•→↑↓!✓◉]|\d+[.)])\s*/u, "").trim())
      .filter(Boolean);
    return lines.length > 1 ? lines : [value.trim()];
  }

  async function applyUpdates(msgIdx: number, updates: ProposedUpdate[]) {
    const newThesis: Record<string, string | string[]> = {
      ...(overrides.thesis ?? {}),
    };
    let bmpAnswers: BMPAnswerOverride[] | null = null;
    let fisherPoints: FisherPointOverride[] | null = null;
    const skipped: string[] = [];

    for (const u of updates) {
      // Thesis sections — accept both 'thesis.bull_case' and bare 'bull_case'
      const thesisKey = u.field.startsWith("thesis.") ? u.field.slice(7) : u.field;
      if (THESIS_KEYS.has(thesisKey)) {
        newThesis[thesisKey] = ARRAY_FIELDS.has(thesisKey)
          ? toListItems(u.new_value)
          : u.new_value;
        continue;
      }

      // BMP rating: bmp.answers.<idx>.rating
      const bmpMatch = u.field.match(/^bmp\.answers\.(\d+)\.rating$/);
      if (bmpMatch) {
        const idx = parseInt(bmpMatch[1], 10);
        const rating = u.new_value.trim().toUpperCase();
        if (idx < bmp.answers.length && rating in BMP_RATING_SCORE) {
          bmpAnswers ??=
            overrides.bmp?.answers?.length
              ? overrides.bmp.answers.map((a) => ({ ...a }))
              : bmp.answers.map((a) => ({
                  label: a.label,
                  rating: a.rating,
                  reasoning: a.reasoning,
                  user_note: "",
                }));
          bmpAnswers[idx] = {
            ...bmpAnswers[idx],
            rating: rating as BMPAnswerOverride["rating"],
          };
          continue;
        }
      }

      // Fisher score: fisher.points.<idx>.score
      const fisherMatch = u.field.match(/^fisher\.points\.(\d+)\.score$/);
      if (fisherMatch) {
        const idx = parseInt(fisherMatch[1], 10);
        const score = parseFloat(u.new_value);
        if (idx < fisher.points.length && [0, 0.5, 0.75, 1].includes(score)) {
          fisherPoints ??=
            overrides.fisher?.points?.length
              ? overrides.fisher.points.map((p) => ({ ...p }))
              : fisher.points.map((p) => ({
                  key: p.key,
                  label: p.label,
                  score: p.score,
                  reasoning: p.reasoning,
                  user_note: "",
                }));
          fisherPoints[idx] = { ...fisherPoints[idx], score };
          continue;
        }
      }

      skipped.push(u.field);
    }

    const updated: AnalysisOverrides = { ...overrides };
    if (Object.keys(newThesis).length) {
      updated.thesis = newThesis as AnalysisOverrides["thesis"];
    }
    if (bmpAnswers) {
      const score = bmpAnswers.reduce((s, a) => s + BMP_RATING_SCORE[a.rating], 0);
      updated.bmp = { answers: bmpAnswers, score, verdict: bmpVerdict(score) };
    }
    if (fisherPoints) {
      const total = fisherPoints.reduce((s, p) => s + p.score, 0);
      updated.fisher = { points: fisherPoints, total, rating: fisherRating(total) };
    }

    try {
      await saveOverrides(analysisId, updated);
      onOverridesChange(updated);
      setMessages((prev) =>
        prev.map((m, i) => (i === msgIdx ? { ...m, updatesApplied: true } : m))
      );
      patchChatMessage(analysisId, msgIdx, { updates_applied: true }).catch(() => {});
      setError(
        skipped.length
          ? `Some updates could not be applied (unrecognised fields): ${skipped.join(", ")}`
          : null
      );
    } catch (e) {
      console.error("Failed to apply updates", e);
      setError("Failed to save updates — please try again.");
    }
  }

  function dismissUpdates(msgIdx: number) {
    setMessages((prev) =>
      prev.map((m, i) => (i === msgIdx ? { ...m, proposed_updates: undefined } : m))
    );
    patchChatMessage(analysisId, msgIdx, { dismissed: true }).catch(() => {});
  }

  return (
    <div className="bg-slate-800 rounded-xl overflow-hidden mt-6">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-300 flex-1">
          Ask a follow-up about {company} ({ticker})
        </h3>
        <span className="flex items-center gap-1 text-xs text-slate-500">
          <Globe className="w-3 h-3" /> Web search enabled
        </span>
      </div>

      {/* Message history */}
      <div className="p-4 space-y-4 max-h-[500px] overflow-y-auto">
        {messages.length === 0 && !loading && historyLoaded && (
          <div className="space-y-2">
            <p className="text-slate-500 text-sm">Suggested questions:</p>
            <div className="flex flex-wrap gap-2">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1.5 rounded-full transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-700 text-slate-100"
              }`}
            >
              {msg.content}
            </div>

            {/* Source links */}
            {msg.sources && msg.sources.length > 0 && (
              <div className="max-w-[85%] mt-1.5 flex flex-wrap gap-1.5">
                {msg.sources.map((src, si) => (
                  <a
                    key={si}
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 bg-slate-700/60 px-2 py-0.5 rounded-full transition-colors"
                  >
                    <Globe className="w-2.5 h-2.5" />
                    {src.title.length > 40 ? src.title.slice(0, 40) + "…" : src.title}
                  </a>
                ))}
              </div>
            )}

            {/* Proposed updates card */}
            {msg.proposed_updates && msg.proposed_updates.length > 0 && !msg.updatesApplied && (
              <div className="max-w-[85%] mt-2 bg-amber-950/40 border border-amber-700/40 rounded-xl p-3 space-y-2 text-xs">
                <p className="font-semibold text-amber-300">
                  Proposed thesis updates ({msg.proposed_updates.length})
                </p>
                {msg.proposed_updates.map((u, ui) => (
                  <div key={ui} className="space-y-0.5">
                    <p className="font-mono text-amber-400/80">{u.field}</p>
                    {u.old_value && (
                      <p className="text-slate-400 line-through">{u.old_value}</p>
                    )}
                    <p className="text-slate-200">{u.new_value}</p>
                    <p className="text-slate-500 italic">{u.reason}</p>
                  </div>
                ))}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => applyUpdates(i, msg.proposed_updates!)}
                    className="flex items-center gap-1 bg-emerald-700 hover:bg-emerald-600 text-white px-3 py-1 rounded-lg transition-colors"
                  >
                    <Check className="w-3 h-3" /> Accept
                  </button>
                  <button
                    onClick={() => dismissUpdates(i)}
                    className="flex items-center gap-1 bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1 rounded-lg transition-colors"
                  >
                    <X className="w-3 h-3" /> Dismiss
                  </button>
                </div>
              </div>
            )}

            {msg.updatesApplied && (
              <p className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                <Check className="w-3 h-3" /> Changes applied
              </p>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-700 rounded-xl px-3 py-2">
              <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
            </div>
          </div>
        )}

        {error && (
          <p className="text-red-400 text-xs text-center">{error}</p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-700">
        {/* Attached file pill */}
        {attachedFile && (
          <div className="px-4 pt-2 flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-xs bg-slate-700 text-slate-200 px-2.5 py-1 rounded-full">
              <Paperclip className="w-3 h-3 text-blue-400" />
              {attachedFile.name}
              <button
                onClick={() => setAttachedFile(null)}
                className="ml-1 text-slate-400 hover:text-white"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          </div>
        )}
        <div className="px-4 py-3 flex gap-2">
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.xlsx,.xls,.csv,.txt,.md"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) setAttachedFile(f);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            title="Attach a file (.pdf, .xlsx, .csv, .txt)"
            className="text-slate-400 hover:text-slate-200 disabled:opacity-50 p-2 rounded-lg transition-colors"
          >
            <Paperclip className="w-4 h-4" />
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
            placeholder="Ask a follow-up question..."
            disabled={loading}
            className="flex-1 bg-slate-700 text-white text-sm rounded-lg px-3 py-2 placeholder-slate-500 outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white p-2 rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
