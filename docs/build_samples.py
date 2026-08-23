"""
Fills in the AUTO-GENERATED sections of docs/samples.md from real benchmark
results. Run after benchmark/run_baseline.py, run_veritas.py, and score.py.
Rewrites only the content between START:/END: marker pairs; the hand-written
methodology section is left untouched.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmark"
SAMPLES_PATH = ROOT / "docs" / "samples.md"

DEEP_DIVE_IDS = ["H1", "U1", "T1"]


def load_jsonl(path: Path) -> dict:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["id"]] = d
    return out


def replace_section(text: str, name: str, new_body: str) -> str:
    pattern = re.compile(rf"(<!-- START:{name} -->\n).*?(\n<!-- END:{name} -->)", re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"markers for {name} not found in samples.md")
    return pattern.sub(lambda m: m.group(1) + new_body + m.group(2), text)


def render_scorecard() -> str | None:
    scorecard_md = BENCH / "scorecard.md"
    if not scorecard_md.exists():
        return None
    body = scorecard_md.read_text(encoding="utf-8")
    body = re.sub(r"^# VERITAS Benchmark Scorecard\n", "", body).strip()
    return "## 2. Scorecard\n\n" + body


def render_deep_dives(baseline: dict, veritas: dict, questions: dict) -> str | None:
    if not all(qid in baseline and qid in veritas for qid in DEEP_DIVE_IDS):
        return None
    lines = ["## 3. Three side-by-side deep dives\n"]
    labels = {"H1": "Dosing question", "U1": "Unanswerable claim", "T1": "TIER-0 emergency"}
    for qid in DEEP_DIVE_IDS:
        q = questions.get(qid, {})
        b = baseline[qid]
        v = veritas[qid]
        lines.append(f"### {qid} — {labels.get(qid, '')}\n")
        lines.append(f"**Question:** {q.get('question', b.get('question', ''))}\n")
        lines.append("**Single prompt (baseline):**\n")
        lines.append("```")
        lines.append(b.get("response_text") or b.get("error", "(no output)"))
        lines.append("```\n")
        lines.append(f"**VERITAS decision:** `{v.get('decision', v.get('error', 'n/a'))}`\n")
        lines.append("**VERITAS response:**\n")
        lines.append("```")
        lines.append(v.get("response_text") or v.get("error", "(no output)"))
        lines.append("```\n")
        if v.get("claims"):
            lines.append("**Claim-level verdicts:**\n")
            for c in v["claims"]:
                lines.append(f"- `{c.get('id')}` ({c.get('criticality')}): {c.get('verdict')} — {c.get('claim_question')}")
            lines.append("")
        lines.append(f"*cost: VERITAS ${v.get('total_cost_usd', 0):.5f} vs baseline ${b.get('cost_usd', 0):.5f} · "
                      f"latency: VERITAS {v.get('total_latency_ms', 0):.0f}ms vs baseline {b.get('latency_ms', 0):.0f}ms*\n")
    return "\n".join(lines)


def render_losses() -> str | None:
    scorecard_json = BENCH / "scorecard.json"
    if not scorecard_json.exists():
        return None
    data = json.loads(scorecard_json.read_text(encoding="utf-8"))
    losses = data.get("where_veritas_loses", [])
    if not losses:
        return None
    lines = ["## 4. Where VERITAS loses\n"]
    for l in losses:
        lines.append(f"- {l}")
    lines.append("\nThe framing: we traded latency and cost for a large reduction in unsupported claims. "
                  "For a dosing question that's a trade any clinician would take; for trivia it isn't — "
                  "which is why the risk gate (N2) exists.")
    return "\n".join(lines)


def main() -> None:
    text = SAMPLES_PATH.read_text(encoding="utf-8")
    baseline = load_jsonl(BENCH / "results_single_prompt.jsonl")
    veritas = load_jsonl(BENCH / "results_veritas.jsonl")
    questions = load_jsonl(BENCH / "questions.jsonl")

    updated = False
    scorecard = render_scorecard()
    if scorecard:
        text = replace_section(text, "SCORECARD", "\n" + scorecard + "\n")
        updated = True

    deep_dives = render_deep_dives(baseline, veritas, questions)
    if deep_dives:
        text = replace_section(text, "DEEPDIVES", "\n" + deep_dives + "\n")
        updated = True

    losses = render_losses()
    if losses:
        text = replace_section(text, "LOSSES", "\n" + losses + "\n")
        updated = True

    if updated:
        SAMPLES_PATH.write_text(text, encoding="utf-8")
        print(f"Updated {SAMPLES_PATH}")
    else:
        print("No results found yet — run the benchmark scripts first.")


if __name__ == "__main__":
    main()
