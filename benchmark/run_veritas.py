"""
Runs the full VERITAS pipeline over benchmark/questions.jsonl and writes
benchmark/results_veritas.jsonl, including every intermediate node output
(the full run log) so a judge can spot-check any answer. Resumable: a
question only counts as done if the pipeline actually reached a decision
(ANSWER/PARTIAL_ANSWER/REFUSE/HALT) — a run that crashed mid-pipeline (e.g.
hit a rate limit before N7) has `decision: null` and is retried, not
permanently marked done.
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


def load_existing() -> dict[str, dict]:
    """Returns id -> record for every question already attempted, success or error."""
    if not RESULTS_PATH.exists():
        return {}
    existing: dict[str, dict] = {}
    for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            existing[d["id"]] = d
    return existing


def is_success(record: dict) -> bool:
    return "error" not in record and record.get("decision") is not None


def write_all(records: dict[str, dict]) -> None:
    with open(RESULTS_PATH, "w", encoding="utf-8") as out:
        for d in records.values():
            out.write(json.dumps(d, ensure_ascii=False) + "\n")


async def main() -> None:
    questions = load_questions()
    records = load_existing()

    for q in questions:
        existing = records.get(q["id"])
        if existing and is_success(existing):
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
            if run.decision is None:
                print(f"       -> pipeline did not reach a decision (will retry on next run)")
        except Exception as e:  # noqa: BLE001 - one failed question must not kill the whole run
            record = {
                "id": q["id"],
                "question": q["question"],
                "bucket": q["bucket"],
                "tier_gold": q["tier"],
                "answerable_gold": q["answerable"],
                "error": str(e),
            }
            print(f"       -> error: {e}")
        records[q["id"]] = record
        write_all(records)

    n_ok = sum(1 for d in records.values() if is_success(d))
    print(f"\nDone. {n_ok}/{len(questions)} succeeded. Results -> {RESULTS_PATH}")
    print("(Full per-node logs also written individually to logs/<run_id>.json)")


if __name__ == "__main__":
    asyncio.run(main())
