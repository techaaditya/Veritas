"""
Runs the full VERITAS pipeline over benchmark/questions.jsonl and writes
benchmark/results_veritas.jsonl, including every intermediate node output
(the full run log) so a judge can spot-check any answer. Resumable like
run_baseline.py.
"""
import asyncio
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veritas.orchestrator import run as run_pipeline

QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
RESULTS_PATH = Path(__file__).parent / "results_veritas.jsonl"


def load_questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def already_done() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()
    done = set()
    for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            done.add(json.loads(line)["id"])
    return done


async def main() -> None:
    questions = load_questions()
    done = already_done()
    mode = "a" if RESULTS_PATH.exists() else "w"

    with open(RESULTS_PATH, mode, encoding="utf-8") as out:
        for q in questions:
            if q["id"] in done:
                print(f"[skip] {q['id']} (already answered)")
                continue
            print(f"[run]  {q['id']}: {q['question'][:60]}")
            try:
                run = await run_pipeline(q["question"])
                record = {
                    "id": q["id"],
                    "question": q["question"],
                    "bucket": q["bucket"],
                    "tier_gold": q["tier"],
                    "answerable_gold": q["answerable"],
                    **run.to_json(),
                }
            except Exception as e:  # noqa: BLE001 - one failed question must not kill the whole run
                record = {
                    "id": q["id"],
                    "question": q["question"],
                    "bucket": q["bucket"],
                    "tier_gold": q["tier"],
                    "answerable_gold": q["answerable"],
                    "error": str(e),
                }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

    print(f"\nDone. Results -> {RESULTS_PATH}")
    print("(Full per-node logs also written individually to logs/<run_id>.json)")


if __name__ == "__main__":
    asyncio.run(main())
