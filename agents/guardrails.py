# Atlas Guardrails

INVALID_QUOTE_TYPES = {
    "ETF",
    "MUTUALFUND",
    "INDEX",
    "CURRENCY",
    "CRYPTOCURRENCY",
    "FUTURE",
    "OPTION",
}

SPAC_KEYWORDS = {"acquisition", "blank check", "special purpose"}

_TYPE_LABELS = {
    "ETF":            "an ETF",
    "MUTUALFUND":     "a mutual fund",
    "INDEX":          "an index",
    "CURRENCY":       "a currency",
    "CRYPTOCURRENCY": "a cryptocurrency",
    "FUTURE":         "a futures contract",
    "OPTION":         "an options contract",
}


# -- Guardrail 1: Input Validation ---------------------------------------------

def check_security_type(ticker: str, info: dict) -> str | None:
    """
    Return an error string if the ticker is not an investable equity.
    Returns None if the ticker is valid.

    Checks:
    - quoteType is not ETF / MUTUALFUND / INDEX / CURRENCY / CRYPTOCURRENCY /
      FUTURE / OPTION
    - company name does not contain SPAC keywords
    """
    quote_type = (info.get("quoteType") or "").upper()
    long_name  = (info.get("longName") or info.get("shortName") or "").lower()
    display    = info.get("longName") or info.get("shortName") or ticker

    if quote_type in INVALID_QUOTE_TYPES:
        label = _TYPE_LABELS.get(quote_type, f"a {quote_type.lower()}")
        return (
            f"[INPUT ERROR] {ticker} resolves to {label} ({display}).\n"
            f"  Atlas only analyses individual equities. "
            f"Please provide a company name or stock ticker."
        )

    if any(kw in long_name for kw in SPAC_KEYWORDS):
        return (
            f"[INPUT ERROR] {ticker} appears to be a SPAC or shell company ({display}).\n"
            f"  Atlas only analyses operating businesses. "
            f"Please provide a company name or stock ticker."
        )

    return None


# -- Shared warning printer ----------------------------------------------------

def print_warnings(warnings: list, label: str = "GUARDRAIL") -> None:
    """Print a formatted warning block to the terminal."""
    if not warnings:
        return
    suffix = "s" if len(warnings) > 1 else ""
    print(f"\n  [{label}] Warning{suffix}:")
    for w in warnings:
        print(f"  ! {w}")
    print()
