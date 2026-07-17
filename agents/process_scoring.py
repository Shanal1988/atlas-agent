# Stage - Process Scoring (user's investing process frameworks)
#
# Orchestrates: Feroldi Quality Score (+ derived Anti-Fragile) -> Ten Vital
# Signs -> Quality Score Screen -> Investment Stage + Lynch classification.
# Computes the position-sizing synthesis inputs consumed by risk_scoring:
# stage_cap_pct, antifragile_ok, feroldi_band, price_veto.

from agents import feroldi as feroldi_agent
from agents import vital_signs as vital_signs_agent
from agents import quality_screen as quality_screen_agent
from agents import stage_classifier
from agents.context import compute_oey

W = 44


def _print_feroldi(f: dict, af: dict) -> None:
    print(f"\n{'=' * W}")
    print("  ATLAS: FEROLDI QUALITY SCORE")
    print(f"{'=' * W}")
    for sec in f["sections"]:
        print(f"  {sec['label']:<22} {sec['score']:>5} / {sec['max']}")
    print(f"  {'-' * (W - 4)}")
    print(f"  Pre-Gauntlet:          {f['pre_gauntlet']} / 100  "
          f"(raw {f['pre_gauntlet_raw']} / {f['max_effective']})")
    deductions = [g for g in f["gauntlet_items"] if g["score"] < 0]
    if deductions:
        print("  Gauntlet deductions:")
        for g in deductions:
            print(f"    {g['label']:<22} {g['score']}")
    print(f"  Gauntlet:              {f['gauntlet']}")
    print(f"  TOTAL:                 {f['total']} / 100   [{f['band']}]")
    if f["data_gaps"]:
        print(f"  Data gaps (excluded): {', '.join(f['data_gaps'])}")
    print(f"\n  ANTI-FRAGILE SCORE:    {af['total']}  (range -7..17)   [{af['band']}]")
    print(f"{'=' * W}\n")


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

    feroldi, antifragile = feroldi_agent.run(profile)
    _print_feroldi(feroldi, antifragile)

    vitals = vital_signs_agent.run(profile, bmp_result, fisher_result, valuation_result)
    _print_vitals(vitals)

    quality = quality_screen_agent.run(profile)
    _print_quality(quality)

    stage = stage_classifier.run(profile)
    _print_stage(stage)

    oey = compute_oey(profile)
    notes = []
    antifragile_ok = antifragile["total"] >= 7
    if not antifragile_ok:
        notes.append(f"Anti-Fragile {antifragile['total']} < 7 — process says IGNORE (position forced to 0%).")
    if oey["price_veto"]:
        notes.append(f"Operating earnings yield {oey['active_oey']}% < 5% — price veto (wait for Mr. Market).")
    if not stage["do_invest"]:
        notes.append(f"Stage {stage['stage_number']} ({stage['stage_label']}) — process says do not invest.")

    position_sizing = {
        "stage_cap_pct": stage["stage_cap_pct"],
        "antifragile_ok": antifragile_ok,
        "feroldi_band": feroldi["band"],
        "price_veto": oey["price_veto"],
        "active_oey": oey["active_oey"],
        "crushability_pct": None,   # filled by risk_scoring
        "final_pct": None,          # filled by risk_scoring
        "notes": notes,
    }

    return {
        "feroldi": feroldi,
        "antifragile": antifragile,
        "vital_signs": vitals,
        "quality_screen": quality,
        "stage": stage,
        "position_sizing": position_sizing,
    }
