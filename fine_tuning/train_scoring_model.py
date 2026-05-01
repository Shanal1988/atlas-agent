"""
Fine-Tuning — Scoring Model Trainer

Uploads a JSONL training file to the OpenAI Files API, starts a fine-tuning
job on gpt-4o-mini, polls until completion, and prints the resulting model ID.

Requires OPENAI_API_KEY in .env.

Usage:
    python fine_tuning/train_scoring_model.py --stage bmp
    python fine_tuning/train_scoring_model.py --stage selection
    python fine_tuning/train_scoring_model.py --stage risk

After the job completes, add the printed model ID to your .env:
    OPENAI_FT_BMP_MODEL=ft:gpt-4o-mini-2024-07-18:...:...
    OPENAI_FT_SELECTION_MODEL=ft:gpt-4o-mini-2024-07-18:...:...
    OPENAI_FT_RISK_MODEL=ft:gpt-4o-mini-2024-07-18:...:...

The pipeline will then use the fine-tuned model for that stage automatically.
If the env var is not set, Groq is used as before — no other changes needed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

_TRAINING_DIR = Path(__file__).parent / "training_data"
_BASE_MODEL   = "gpt-4o-mini-2024-07-18"
_MIN_EXAMPLES = 10   # OpenAI minimum for fine-tuning

_STAGE_ENV_VARS = {
    "bmp":       "OPENAI_FT_BMP_MODEL",
    "selection": "OPENAI_FT_SELECTION_MODEL",
    "risk":      "OPENAI_FT_RISK_MODEL",
}


def _count_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload training data and start OpenAI fine-tuning job")
    parser.add_argument("--stage", required=True, choices=list(_STAGE_ENV_VARS),
                        help="Which scoring stage to fine-tune")
    parser.add_argument("--no-poll", action="store_true",
                        help="Start job and exit without polling for completion")
    args = parser.parse_args()

    stage    = args.stage
    env_var  = _STAGE_ENV_VARS[stage]
    jsonl    = _TRAINING_DIR / f"{stage}_training.jsonl"

    # -- Pre-flight checks --
    if not jsonl.exists():
        print(f"Training file not found: {jsonl}")
        print(f"Run: python fine_tuning/prepare_scoring_data.py  first.")
        sys.exit(1)

    n = _count_lines(jsonl)
    print(f"\nTraining file: {jsonl}  ({n} examples)")

    if n < _MIN_EXAMPLES:
        print(f"Error: OpenAI requires at least {_MIN_EXAMPLES} training examples. Found {n}.")
        print("Accumulate more theses and re-run prepare_scoring_data.py.")
        sys.exit(1)

    if n < 50:
        print(f"Warning: {n} examples is below the recommended 50+ for meaningful improvement.")
        confirm = input("Continue anyway? [y/N] ").strip().lower()
        if confirm != "y":
            sys.exit(0)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set in .env")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("openai package not installed. Run: pip install openai")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # -- Upload training file --
    print(f"\nUploading {jsonl.name} to OpenAI Files API...")
    with open(jsonl, "rb") as f:
        file_obj = client.files.create(file=f, purpose="fine-tune")
    file_id = file_obj.id
    print(f"  File ID: {file_id}")

    # -- Create fine-tuning job --
    print(f"\nCreating fine-tuning job on {_BASE_MODEL}...")
    job = client.fine_tuning.jobs.create(
        training_file=file_id,
        model=_BASE_MODEL,
        hyperparameters={"n_epochs": "auto"},
    )
    job_id = job.id
    print(f"  Job ID:  {job_id}")
    print(f"  Status:  {job.status}")

    if args.no_poll:
        print(f"\nPolling skipped (--no-poll). Check status manually:")
        print(f"  from openai import OpenAI; OpenAI().fine_tuning.jobs.retrieve('{job_id}')")
        return

    # -- Poll until completion --
    print("\nPolling for completion (this typically takes 10–60 minutes)...")
    poll_interval = 60   # seconds
    elapsed = 0
    timeout = 7200       # 2 hours

    while elapsed < timeout:
        time.sleep(poll_interval)
        elapsed += poll_interval
        job = client.fine_tuning.jobs.retrieve(job_id)
        status = job.status
        print(f"  [{elapsed // 60}m] Status: {status}")

        if status == "succeeded":
            model_id = job.fine_tuned_model
            print(f"\nFine-tuning succeeded!")
            print(f"  Model ID: {model_id}")
            print(f"\nAdd this to your .env:")
            print(f"  {env_var}={model_id}")
            print(f"\nThe pipeline will use this model for the {stage.upper()} stage")
            print(f"on the next run. Groq remains the fallback if the env var is removed.")
            return

        if status in ("failed", "cancelled"):
            print(f"\nFine-tuning {status}.")
            events = client.fine_tuning.jobs.list_events(job_id, limit=5)
            for e in events.data:
                print(f"  {e.created_at}: {e.message}")
            sys.exit(1)

    print(f"\nTimed out after {timeout // 60} minutes. Job {job_id} may still be running.")
    print(f"Check status: client.fine_tuning.jobs.retrieve('{job_id}')")
    sys.exit(1)


if __name__ == "__main__":
    main()
