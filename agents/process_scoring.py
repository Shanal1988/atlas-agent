# Stage - Process Scoring (user's investing process frameworks)
#
# Orchestrates: Ten Vital Signs -> Quality Score Screen ->
# Investment Stage + Lynch classification.
# Computes the position-sizing synthesis inputs consumed by risk_scoring:
# stage_cap_pct, price_veto.

from agents import vital_signs as vital_signs_agent
from agents import quality_screen as quality_screen_agent
from agents import stage_classifier
from agents.context import compute_oey

W = 44


def _print_vitals(v: dict) -> None:
    print(f"\n{'=' * W}")
    print("  ATLAS: TEN VITAL SIGNS")
    print(f"{'=' * W}")
    for it in v["items"]:
        print(f"  [{it['score']:>3}] {it['label']}")
    print(f"  {'-' * (W - 4)}")
    print(f"  TOTAL: {v['total']} / 10")
    print(f"  Sane valuation?   {v['closing']['sane_valuation']}")
    print(f"  Opportunity cost: {v['closing']['opportunity_cost']}")
    print(f"{'=' * W}\n")


def _print_quality(q: dict) -> None:
    print(f"\n{'=' * W}")
    print("  ATLAS: QUALITY SCORE SCREEN")
    print(f"{'=' * W}")
    print(f"  Qualitative:  {q['qualitative']['total']} / {q['qualitative']['max']}")
    print(f"  Quantitative: {q['quantitative']['total']} / {q['quantitative']['max']}")
    print(f"  Valuation:    {q['valuation']['total']} / {q['valuation']['max']}")
    print(f"  {'-' * (W - 4)}")
    print(f"  OVERALL RANK SCORE: {q['overall']}")
    if q["data_gaps"]:
        print(f"  Data gaps: {', '.join(q['data_gaps'])}")
    print(f"{'=' * W}\n")


def _print_stage(s: dict) -> None:
    print(f"\n{'=' * W}")
    print("  ATLAS: INVESTMENT STAGE")
    print(f"{'=' * W}")
    print(f"  Stage {s['stage_number']}: {s['stage_label']}")
    print(f"  Risk: {s['risk']}   Profits: {s['profits']}   Potential: {s['return_potential']}")
    print(f"  Allocation guidance: {s['allocation_guidance']}  (cap {s['stage_cap_pct']}%)")
    print(f"  Lynch: {s['lynch_category']}  ({s['lynch_attributes']}; alloc {s['lynch_allocation']})")
    print(f"  {s['reasoning']}")
    print(f"{'=' * W}\n")


def run(profile: dict, bmp_result: dict | None, fisher_result: dict | None,
        selection_result: dict | None, valuation_result: dict | None) -> dict:
    company = profile.get("name") or profile.get("ticker", "Unknown")
    print(f"\n  [Process] Running investing-process scorecards for {company}...")

    vitals = vital_signs_agent.run(profile, bmp_result, fisher_result, valuation_result)
    _print_vitals(vitals)

    quality = quality_screen_agent.run(profile)
    _print_quality(quality)

    stage = stage_classifier.run(profile)
    _print_stage(stage)

    oey = compute_oey(profile)
    notes = []
    if oey["price_veto"]:
        notes.append(f"Operating earnings yield {oey['active_oey']}% < 5% — price veto (wait for Mr. Market).")
    if not stage["do_invest"]:
        notes.append(f"Stage {stage['stage_number']} ({stage['stage_label']}) — process says do not invest.")

    position_sizing = {
        "stage_cap_pct": stage["stage_cap_pct"],
        "price_veto": oey["price_veto"],
        "active_oey": oey["active_oey"],
        "crushability_pct": None,   # filled by risk_scoring
        "final_pct": None,          # filled by risk_scoring
        "notes": notes,
    }

    return {
        "vital_signs": vitals,
        "quality_screen": quality,
        "stage": stage,
        "position_sizing": position_sizing,
    }
