"""
Fine-Tuning — Thesis Style Model Trainer

Uploads style training data to the OpenAI Files API and fine-tunes gpt-4o-mini
on (structured context -> thesis sections) pairs.

Requires OPENAI_API_KEY in .env.

Usage:
    python fine_tuning/train_style_model.py

After the job completes, add the printed model ID to your .env:
    OPENAI_FT_THESIS_MODEL=ft:gpt-4o-mini-2024-07-18:...:...
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

_TRAINING_FILE = Path(__file__).parent / "training_data" / "style_training.jsonl"
_BASE_MODEL    = "gpt-4o-mini-2024-07-18"
_MIN_EXAMPLES  = 10


def _count_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> None:
    if not _TRAINING_FILE.exists():
        print(f"Training file not found: {_TRAINING_FILE}")
        print("Run: python fine_tuning/prepare_style_data.py  first.")
        sys.exit(1)

    n = _count_lines(_TRAINING_FILE)
    print(f"\nStyle training file: {_TRAINING_FILE}  ({n} examples)")

    if n < _MIN_EXAMPLES:
        print(f"Error: OpenAI requires at least {_MIN_EXAMPLES} examples. Found {n}.")
        sys.exit(1)

    if n < 20:
        print(f"Warning: {n} examples is below the recommended 20+ for style fine-tuning.")
        print("Consider adding more edited examples to data/style_examples/edited/")
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

    print(f"\nUploading {_TRAINING_FILE.name} to OpenAI Files API...")
    with open(_TRAINING_FILE, "rb") as f:
        file_obj = client.files.create(file=f, purpose="fine-tune")
    file_id = file_obj.id
    print(f"  File ID: {file_id}")

    print(f"\nCreating fine-tuning job on {_BASE_MODEL}...")
    job = client.fine_tuning.jobs.create(
        training_file=file_id,
        model=_BASE_MODEL,
        hyperparameters={"n_epochs": "auto"},
    )
    job_id = job.id
    print(f"  Job ID:  {job_id}")
    print(f"  Status:  {job.status}")

    print("\nPolling for completion...")
    poll_interval = 60
    elapsed = 0
    timeout = 7200

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
            print(f"\nAdd to your .env:")
            print(f"  OPENAI_FT_THESIS_MODEL={model_id}")
            return

        if status in ("failed", "cancelled"):
            print(f"\nFine-tuning {status}.")
            events = client.fine_tuning.jobs.list_events(job_id, limit=5)
            for e in events.data:
                print(f"  {e.created_at}: {e.message}")
            sys.exit(1)

    print(f"\nTimed out after {timeout // 60} minutes.")
    sys.exit(1)


if __name__ == "__main__":
    main()
