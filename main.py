import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure stdout uses UTF-8 on Windows so LLM-generated Unicode (em dashes etc.)
# doesn't crash with cp1252 UnicodeEncodeError. Unknown chars are replaced with '?'.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agents.discovery import run as discover
from agents.industry_analysis import run as industry_analysis
from agents.bmp_gate import run as bmp_gate
from agents.fisher import run as fisher
from agents.stock_selection import run as stock_selection
from agents.risk_scoring import run as risk_scoring
from agents.thesis_writer import run as thesis_writer
from agents.valuation import run as valuation
from agents.similar_companies import run as similar_companies


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <company name>")
        sys.exit(1)

    company_name      = " ".join(sys.argv[1:])
    profile           = discover(company_name)
    industry_result   = industry_analysis(profile)
    bmp_result        = bmp_gate(profile)
    fisher_result     = fisher(profile, bmp_result["verdict"])
    selection_result  = stock_selection(profile, bmp_result["verdict"])
    risk_result       = risk_scoring(profile, bmp_result, fisher_result, selection_result)
    valuation_result  = valuation(profile)
    similar_result    = similar_companies(profile, industry_result)
    thesis_writer(profile, bmp_result, fisher_result, selection_result, risk_result,
                  valuation_result, industry_result, similar_result)


if __name__ == "__main__":
    main()
