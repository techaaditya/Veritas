"""
Runs the fair single-prompt baseline over benchmark/questions.jsonl and writes
benchmark/results_single_prompt.jsonl. Resumable: only questions with a
successful prior result are skipped on rerun — a question that previously
errored (e.g. hit a rate limit) is retried, not permanently marked done. The
underlying LLM call is also disk-cached, so successful reruns are cheap.
"""
import io
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veritas import baseline

QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"
RESULTS_PATH = Path(__file__).parent / "results_single_prompt.jsonl"


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


def write_all(records: dict[str, dict]) -> None:
    with open(RESULTS_PATH, "w", encoding="utf-8") as out:
        for d in records.values():
            out.write(json.dumps(d, ensure_ascii=False) + "\n")


def main() -> None:
    questions = load_questions()
    records = load_existing()

    for q in questions:
        existing = records.get(q["id"])
        if existing and "error" not in existing:
            print(f"[skip] {q['id']} (already answered)")
            continue
        print(f"[run]  {q['id']}: {q['question'][:60]}")
        try:
            result = baseline.run(q["question"])
            record = {
                "id": q["id"],
                "question": q["question"],
                "bucket": q["bucket"],
                "tier": q["tier"],
                "answerable": q["answerable"],
                "response_text": result.text,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
                "cached": result.cached,
            }
        except Exception as e:  # noqa: BLE001 - a single failed question must not kill the whole run
            record = {"id": q["id"], "question": q["question"], "bucket": q["bucket"], "tier": q["tier"], "answerable": q["answerable"], "error": str(e)}
            print(f"       -> error: {e}")
        records[q["id"]] = record
        write_all(records)

    n_ok = sum(1 for d in records.values() if "error" not in d)
    print(f"\nDone. {n_ok}/{len(questions)} succeeded. Results -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
