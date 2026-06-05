# LLM-as-a-Judge -- 4 audit functions for the Atlas pipeline
#
# All judges are non-blocking: they print a [JUDGE] block but never halt execution.
# Judge 1 (score justification), Judge 2 (bull/bear balance), Judge 3 (thesis
# coherence) make Groq calls; Judge 4 (cross-stage consistency) is rule-only.

import os
from dataclasses import dataclass, field
from groq import Groq


GROQ_MODEL = "llama-3.1-8b-instant"


# -- Result type ---------------------------------------------------------------

@dataclass
class JudgeResult:
    judge:    str
    passed:   bool
    severity: str           # "INFO" | "WARN" | "FAIL"
    flags:    list = field(default_factory=list)

    def asdict(self) -> dict:
        return {"passed": self.passed, "severity": self.severity, "flags": list(self.flags)}


# -- Shared printer ------------------------------------------------------------

def print_judge(result: JudgeResult, company: str = "") -> None:
    """Print a formatted [JUDGE] block to the terminal."""
    name = result.judge.replace("_", " ").upper()
    label = f"JUDGE: {name}"
    if company:
        label += f" -- {company}"

    print(f"\n  [{label}]")

    if not result.flags:
        print("  PASS")
        return

    prefix = {"FAIL": "  FAIL", "WARN": "  WARN"}.get(result.severity, "  INFO")
    for flag in result.flags:
        print(f"{prefix} -- {flag}")


# -- Judge 1 -- Score Justification Auditor -------------------------------------

_JUSTIFICATION_SYSTEM = (
    "You are an audit analyst reviewing investment scores against company data. "
    "For each scored item, check whether the score is consistent with the data provided. "
    "Flag only items where the score clearly contradicts the data "
    "(e.g. YES but the data shows losses, or NO but the data shows strong growth). "
    "Format each flag as: [KEY]: INCONSISTENT -- one sentence explanation. "
    "Reply only for items with issues. "
    "If all items are consistent with the data, reply exactly: ALL_CONSISTENT"
)


def audit_score_justification(stage: str, context: str, items: list) -> JudgeResult:
    """
    Judge 1 -- Check if extreme scores are justified by the company data.
    stage : 'BMP' | 'FISHER' | 'SELECTION'
    items : list of score dicts from the agent's parser.
    """
    judge_id = f"score_justification_{stage.lower()}"

    # Select extreme items only (reduces tokens, focuses on highest-impact scores)
    if stage == "FISHER":
        hi = [x for x in items if x.get("score", 0.5) == 1.0][:3]
        lo = [x for x in items if x.get("score", 0.5) == 0.0][:3]
        extreme = hi + lo
    else:
        extreme = [x for x in items if x.get("rating", "").upper() in ("YES", "NO")]

    if len(extreme) < 2:
        return JudgeResult(judge=judge_id, passed=True, severity="INFO")

    # Format items for the prompt
    lines = []
    for item in extreme:
        if stage == "FISHER":
            lines.append(
                f"{item.get('key','?')} {item.get('label','')} "
                f"[score={item.get('score','?')}]: {item.get('reasoning','')}"
            )
        else:
            key = item.get("key") or item.get("label", "?")
            lines.append(
                f"{key} [{item.get('rating','?')}]: {item.get('reasoning','')}"
            )

    user_msg = (
        f"Company data:\n{context}\n\n"
        f"Scored items to audit ({stage} stage -- extreme scores only):\n"
        + "\n".join(lines)
    )

    _msgs = [
        {"role": "system", "content": _JUSTIFICATION_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]
    try:
        raw = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=_msgs, max_tokens=300, temperature=0.1,
        ).choices[0].message.content.strip()
    except Exception:
        from agents.llm_client import gemini_call
        raw = gemini_call(_msgs, max_tokens=300, temperature=0.1)
    if not raw:
        return JudgeResult(judge=judge_id, passed=True, severity="INFO",
                           flags=["Judge unavailable: all LLMs failed"])

    if raw.upper() == "ALL_CONSISTENT":
        return JudgeResult(judge=judge_id, passed=True, severity="INFO")

    flags = [ln.strip() for ln in raw.splitlines() if "INCONSISTENT" in ln.upper()]
    if not flags:
        return JudgeResult(judge=judge_id, passed=True, severity="INFO")

    return JudgeResult(judge=judge_id, passed=False, severity="WARN", flags=flags)


# -- Judge 2 -- Bull/Bear Balance Check -----------------------------------------

_BEAR_SYSTEM = (
    "You are reviewing investment thesis bear case bullets. "
    "Classify each as STRONG, SPECULATIVE, GENERIC, or WEAK.\n\n"
    "Definitions:\n"
    "STRONG -- specific, evidence-grounded risk unique to this company\n"
    "SPECULATIVE -- uses hedging language without data ('could', 'may', 'might')\n"
    "GENERIC -- applies to any company in this sector, not this company specifically\n"
    "WEAK -- acknowledges a risk then immediately dismisses it in the same sentence\n\n"
    "Rules:\n"
    "- Omit STRONG bear points from your reply.\n"
    "- For each non-STRONG point write one line: BEAR_N: LABEL -- your reason here.\n"
    "- Example: BEAR_2: GENERIC -- This risk applies to all software acquirers, not CSU specifically.\n"
    "- If all bear points are STRONG, reply exactly: ALL_STRONG"
)


def check_bull_bear_balance(company: str, bear_case: list) -> JudgeResult:
    """Judge 2 -- Check if bear case bullets are credible and company-specific."""
    non_empty = [b for b in bear_case if b and b.strip()]
    if not non_empty:
        return JudgeResult(judge="bull_bear_balance", passed=False, severity="WARN",
                           flags=["Bear case is empty -- no risks articulated."])

    bears_text = "\n".join(f"BEAR_{i+1}: {b}" for i, b in enumerate(non_empty))
    user_msg = f"Company: {company}\n\nBear case points:\n{bears_text}"

    _msgs = [
        {"role": "system", "content": _BEAR_SYSTEM},
        {"role": "user",   "content": user_msg},
    ]
    try:
        raw = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=_msgs, max_tokens=200, temperature=0.1,
        ).choices[0].message.content.strip()
    except Exception:
        from agents.llm_client import gemini_call
        raw = gemini_call(_msgs, max_tokens=200, temperature=0.1)
    if not raw:
        return JudgeResult(judge="bull_bear_balance", passed=True, severity="INFO",
                           flags=["Judge unavailable: all LLMs failed"])

    if raw.upper() == "ALL_STRONG":
        return JudgeResult(judge="bull_bear_balance", passed=True, severity="INFO")

    flags = [
        ln.strip() for ln in raw.splitlines()
        if any(t in ln.upper() for t in ("SPECULATIVE", "GENERIC", "WEAK"))
    ]
    if not flags:
        return JudgeResult(judge="bull_bear_balance", passed=True, severity="INFO")

    return JudgeResult(judge="bull_bear_balance", passed=False, severity="WARN", flags=flags)


# -- Judge 3 -- Thesis Coherence Check -----------------------------------------

_COHERENCE_SYSTEM = (
    "You are checking whether an investment decision is logically consistent with its scores. "
    "Reply in exactly one sentence starting with CONSISTENT or INCONSISTENT. "
    "If inconsistent, briefly name the specific contradiction."
)


def check_thesis_coherence(
    company: str,
    decision: str,
    bmp_result: dict,
    fisher_result,
    selection_result,
    risk_result: dict,
    valuation_result: dict | None = None,
) -> JudgeResult:
    """
    Judge 3 -- rule-based checks first; Groq only when no rule fires.
    Non-blocking: flags a mismatch but never halts the pipeline.
    """
    category     = risk_result.get("category", "")
    conviction   = (risk_result.get("conviction") or "MEDIUM").upper()
    bmp_verdict  = (bmp_result.get("verdict") or "").upper()
    fisher_total = float((fisher_result or {}).get("total") or 0.0)
    sel_score    = float((selection_result or {}).get("score") or 0.0)

    flags: list = []
    severity     = "INFO"

    # Hard rule: Egg = no position, INVEST is impossible
    if category == "Egg" and decision == "INVEST":
        flags.append("Egg category cannot be INVEST -- position size is 0%.")
        severity = "FAIL"

    # Hard rule: BMP REJECT + INVEST is contradictory
    if "REJECT" in bmp_verdict and decision == "INVEST":
        flags.append("BMP verdict is REJECT but DECISION is INVEST -- contradictory.")
        severity = "FAIL"

    # Warn: exceptional scores but PASS
    if fisher_total >= 12 and sel_score >= 7 and decision == "PASS":
        flags.append(
            f"PASS contradicts exceptional scores "
            f"(Fisher {fisher_total}/15, Selection {sel_score}/8)."
        )
        severity = "WARN"

    # Warn: weak Fisher but INVEST
    if fisher_result is not None and 0 < fisher_total < 6 and decision == "INVEST":
        flags.append(
            f"INVEST despite WEAK Fisher score ({fisher_total}/15) -- "
            f"consider WATCHLIST."
        )
        severity = "WARN"

    # Warn: LOW conviction + INVEST
    if conviction == "LOW" and decision == "INVEST":
        flags.append(
            "LOW conviction but INVEST -- WATCHLIST may better reflect confidence."
        )
        if severity == "INFO":
            severity = "WARN"

    # -- Valuation consistency rules --
    if valuation_result and valuation_result.get("available"):
        mkt   = valuation_result.get("mktcap_mn")
        dh    = valuation_result.get("dhandho", {})
        dc    = valuation_result.get("dcf", {})
        er    = (valuation_result.get("exp_returns") or {})
        dh_lo = ((dh.get("lower")  or {}).get("iv"))
        dh_hi = ((dh.get("higher") or {}).get("iv"))
        dc_iv = dc.get("iv") if dc else None
        er_iv = er.get("iv")
        valid = [v for v in [dh_lo, dh_hi, dc_iv, er_iv] if v and v > 0]
        if valid and mkt and mkt > 0:
            iv_mid   = (min(valid) + max(valid)) / 2
            prem_pct = (mkt - iv_mid) / iv_mid * 100
            if prem_pct > 100 and decision == "INVEST":
                flags.append(
                    f"INVEST at {prem_pct:.0f}% premium to midpoint IV "
                    "-- all 4 models price significantly below market; "
                    "growth assumptions must exceed base case to justify entry."
                )
                if severity == "INFO":
                    severity = "WARN"
            elif 50 < prem_pct <= 100 and conviction in ("LOW", "MEDIUM") and decision == "INVEST":
                flags.append(
                    f"{prem_pct:.0f}% IV premium with {conviction} conviction "
                    "-- valuation is stretched; WATCHLIST until better entry or "
                    "thesis confirms growth well above model assumptions."
                )
                if severity == "INFO":
                    severity = "WARN"
            elif prem_pct < -30 and decision == "PASS":
                flags.append(
                    f"PASS at {abs(prem_pct):.0f}% discount to midpoint IV "
                    "-- significant margin of safety exists; consider WATCHLIST."
                )
                if severity == "INFO":
                    severity = "WARN"

    if flags:
        return JudgeResult(judge="thesis_coherence", passed=False,
                           severity=severity, flags=flags)

    # No rules fired -- brief Groq coherence check
    summary = (
        f"BMP {bmp_result.get('score', 0)}/5 ({bmp_verdict}), "
        f"Fisher {fisher_total}/15, Selection {sel_score}/8, "
        f"Conviction {conviction}, Category {category}, "
        f"Decision {decision}"
    )
    _msgs = [
        {"role": "system", "content": _COHERENCE_SYSTEM},
        {"role": "user",   "content": f"Company: {company}\n{summary}"},
    ]
    try:
        raw = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=GROQ_MODEL, messages=_msgs, max_tokens=80, temperature=0.1,
        ).choices[0].message.content.strip()
    except Exception:
        from agents.llm_client import gemini_call
        raw = gemini_call(_msgs, max_tokens=80, temperature=0.1)
    if not raw:
        return JudgeResult(judge="thesis_coherence", passed=True, severity="INFO",
                           flags=["Judge unavailable: all LLMs failed"])

    if raw.upper().startswith("INCONSISTENT"):
        return JudgeResult(judge="thesis_coherence", passed=False,
                           severity="WARN", flags=[raw])

    return JudgeResult(judge="thesis_coherence", passed=True, severity="INFO")


# -- Judge 4 -- Cross-Stage Consistency -----------------------------------------

def check_cross_stage_consistency(
    fisher_result,
    selection_result,
    risk_result: dict,
) -> JudgeResult:
    """Judge 4 -- rule-based only, zero Groq tokens."""
    fisher_total  = float((fisher_result or {}).get("total") or 0.0)
    sel_score     = float((selection_result or {}).get("score") or 0.0)
    conviction    = (risk_result.get("conviction") or "MEDIUM").upper()
    category      = risk_result.get("category", "")
    base_nos      = risk_result.get("base_nos", 0)
    total_penalty = risk_result.get("total_penalty", 0)
    factors       = risk_result.get("factors", [])

    warn_flags: list = []
    info_flags: list = []

    # Near-perfect scores but LOW conviction
    if fisher_total >= 12 and sel_score >= 7 and conviction == "LOW":
        warn_flags.append(
            f"LOW conviction contradicts near-perfect scores "
            f"(Fisher {fisher_total}/15, Selection {sel_score}/8)."
        )

    # Weak scores but HIGH conviction
    if fisher_result is not None and fisher_total < 7 and sel_score < 4 and conviction == "HIGH":
        warn_flags.append(
            f"HIGH conviction contradicts weak scores "
            f"(Fisher {fisher_total}/15, Selection {sel_score}/8)."
        )

    # Borderline Diamond (close to Gold threshold)
    if category == "Diamond" and base_nos >= 4:
        info_flags.append(
            f"Borderline Diamond ({base_nos} NOs) -- "
            f"1 more NO would move to Gold (4-6%)."
        )

    # All risk factors scored zero -- may be optimistic
    if factors and all(f.get("penalty", 0) == 0 for f in factors):
        info_flags.append(
            "All 5 risk factors scored 0 -- zero penalty may be optimistic; verify manually."
        )

    all_flags = warn_flags + info_flags
    if not all_flags:
        return JudgeResult(judge="cross_stage_consistency", passed=True, severity="INFO")

    severity = "WARN" if warn_flags else "INFO"
    return JudgeResult(
        judge="cross_stage_consistency",
        passed=not bool(warn_flags),
        severity=severity,
        flags=all_flags,
    )
