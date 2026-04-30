import sys
from dotenv import load_dotenv

load_dotenv()

from agents.discovery import run as discover
from agents.bmp_gate import run as bmp_gate


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <company name>")
        sys.exit(1)

    company_name = " ".join(sys.argv[1:])
    profile = discover(company_name)
    bmp_gate(profile)


if __name__ == "__main__":
    main()
