import sys
from dotenv import load_dotenv

load_dotenv()

from agents.discovery import run as discover
from agents.bmp_gate import run as bmp_gate
from agents.fisher import run as fisher
from agents.stock_selection import run as stock_selection
from agents.risk_scoring import run as risk_scoring
from agents.thesis_writer import run as thesis_writer


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <company name>")
        sys.exit(1)

    company_name     = " ".join(sys.argv[1:])
    profile          = discover(company_name)
    bmp_result       = bmp_gate(profile)
    fisher_result    = fisher(profile, bmp_result["verdict"])
    selection_result = stock_selection(profile, bmp_result["verdict"])
    risk_result      = risk_scoring(profile, bmp_result, fisher_result, selection_result)
    thesis_writer(profile, bmp_result, fisher_result, selection_result, risk_result)


if __name__ == "__main__":
    main()
