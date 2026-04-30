import sys
from dotenv import load_dotenv

load_dotenv()

from agents.discovery import run as discover
from agents.bmp_gate import run as bmp_gate
from agents.fisher import run as fisher
from agents.stock_selection import run as stock_selection


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <company name>")
        sys.exit(1)

    company_name = " ".join(sys.argv[1:])
    profile         = discover(company_name)
    bmp_result      = bmp_gate(profile)
    fisher_result   = fisher(profile, bmp_result["verdict"])
    stock_selection(profile, bmp_result["verdict"])


if __name__ == "__main__":
    main()
