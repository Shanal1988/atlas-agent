# Screening criteria — parse "metric op value" rules, filter, and rank.
#
# Rules are plain strings so presets live in YAML and ad-hoc filters can be
# passed on the command line. No eval(): each rule is matched against a fixed
# grammar and an operator table.
#
#   roic_avg >= 15%          percentages become fractions (0.15)
#   market_cap_usd < 5B      K / M / B / T suffixes
#   oey_passes == true       booleans
#   sector not in Financial Services, Real Estate     comma-separated text list

import re
from bisect import bisect_left, bisect_right
from pathlib import Path

import yaml

from agents.screener.metrics import METRICS

PRESET_DIR = Path(__file__).resolve().parent / "presets"

_RULE = re.compile(r"^\s*([a-z_0-9]+)\s*(>=|<=|==|!=|>|<|not in|in)\s*(.+?)\s*$", re.IGNORECASE)
_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
_OPS = {
    ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,  "<":  lambda a, b: a < b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
}


def _parse_value(raw: str):
    s = raw.strip().strip("'\"")
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low.endswith("%"):
        return float(low[:-1]) / 100
    if low and low[-1] in _SUFFIX:
        try:
            return float(low[:-1]) * _SUFFIX[low[-1]]
        except ValueError:
            pass
    try:
        return float(low)
    except ValueError:
        return s


def parse_rule(rule: str) -> dict:
    match = _RULE.match(rule)
    if not match:
        raise ValueError(f"Can't parse rule '{rule}'. Expected 'metric op value', e.g. 'roic_avg >= 15%'.")
    metric, op, raw = match.group(1).lower(), match.group(2).lower(), match.group(3)
    if metric not in METRICS:
        raise ValueError(f"Unknown metric '{metric}' in rule '{rule}'. Run `python screen.py --list-metrics`.")
    if op in ("in", "not in"):
        value = [v.strip().lower() for v in raw.split(",") if v.strip()]
    else:
        value = _parse_value(raw)
        if op in (">=", "<=", ">", "<") and not isinstance(value, (int, float)):
            raise ValueError(f"Rule '{rule}' compares against '{raw}', which is not a number.")
    return {"text": rule.strip(), "metric": metric, "op": op, "value": value}


def parse_weights(specs: list[str]) -> dict:
    """['roic_avg:0.5', 'pe:-0.2'] -> {'roic_avg': 0.5, 'pe': -0.2}"""
    weights = {}
    for spec in specs:
        metric, _, w = spec.partition(":")
        metric = metric.strip().lower()
        if metric not in METRICS:
            raise ValueError(f"Unknown metric '{metric}' in --rank '{spec}'.")
        try:
            weights[metric] = float(w) if w else 1.0
        except ValueError:
            raise ValueError(f"Bad weight in --rank '{spec}'. Use metric:weight, e.g. roic_avg:0.5")
    return weights


def check(rule: dict, row: dict):
    """True / False, or None when the metric is missing for this row."""
    v = row.get(rule["metric"])
    if v is None:
        return None
    op, target = rule["op"], rule["value"]
    if op == "in":
        return str(v).lower() in target
    if op == "not in":
        return str(v).lower() not in target
    if isinstance(v, str) and isinstance(target, str):
        v, target = v.lower(), target.lower()
    try:
        return _OPS[op](v, target)
    except TypeError:
        return None


def apply_filters(rows: list[dict], rules: list[dict], missing: str = "fail") -> tuple[list[dict], list[dict]]:
    """Return (passing rows, per-rule funnel stats). With missing='fail' a row
    lacking data for a rule is excluded; with 'pass' the rule is skipped."""
    stats = [{"rule": r["text"], "failed": 0, "missing": 0} for r in rules]
    passing = []
    for row in rows:
        ok, missing_rules = True, []
        for rule, stat in zip(rules, stats):
            result = check(rule, row)
            if result is None:
                stat["missing"] += 1
                missing_rules.append(rule["metric"])
                if missing == "fail":
                    ok = False
            elif not result:
                stat["failed"] += 1
                ok = False
        if ok:
            passing.append({**row, "missing_for_filters": missing_rules})
    return passing, stats


def rank(rows: list[dict], weights: dict) -> list[dict]:
    """Percentile-weighted composite score 0-100. Negative weight = lower is
    better. A missing metric earns 0 for that component."""
    if not rows:
        return rows
    total_w = sum(abs(w) for w in weights.values()) or 1
    pct: dict = {}
    for metric, w in weights.items():
        vals = sorted(r[metric] for r in rows if isinstance(r.get(metric), (int, float)))
        n = len(vals)
        for r in rows:
            v = r.get(metric)
            if not isinstance(v, (int, float)) or n == 0:
                p = 0.0
            else:
                below = bisect_left(vals, v)
                equal = bisect_right(vals, v) - below
                p = (below + 0.5 * equal) / n  # mid-rank percentile, 0..1
                if w < 0:
                    p = 1 - p
            pct.setdefault(id(r), 0.0)
            pct[id(r)] += abs(w) * p
    for r in rows:
        r["screen_score"] = round(100 * pct.get(id(r), 0.0) / total_w, 1)
    return sorted(rows, key=lambda r: r["screen_score"], reverse=True)


# -- Presets --------------------------------------------------------------------

def list_presets() -> list[dict]:
    out = []
    for path in sorted(PRESET_DIR.glob("*.yaml")):
        p = load_preset(path.stem)
        out.append({"name": path.stem, "description": p.get("description", "")})
    return out


def load_preset(name: str) -> dict:
    path = PRESET_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(p.stem for p in PRESET_DIR.glob("*.yaml"))
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    with open(path, encoding="utf-8") as f:
        preset = yaml.safe_load(f) or {}
    for metric in (preset.get("rank") or {}):
        if metric not in METRICS:
            raise ValueError(f"Preset '{name}' ranks on unknown metric '{metric}'.")
    return preset
