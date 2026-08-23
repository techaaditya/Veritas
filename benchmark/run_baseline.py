"""
Runs the fair single-prompt baseline over benchmark/questions.jsonl and writes
benchmark/results_single_prompt.jsonl. Resumable: already-answered question
ids are skipped on rerun (the underlying LLM call is also disk-cached, so
reruns are cheap either way).
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


def already_done() -> set[str]:
    if not RESULTS_PATH.exists():
        return set()
    done = set()
    for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            done.add(json.loads(line)["id"])
    return done


def main() -> None:
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
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

    print(f"\nDone. Results -> {RESULTS_PATH}")


if __name__ == "__main__":
    main()
