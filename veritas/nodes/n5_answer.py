"""
N5 — Grounded Answerer (per claim). gemini-3.6-flash, temp 0.0.

Beyond the prompt's own instruction not to fabricate numbers, we enforce it in
code: any number appearing in `answer` that is not literally present in
`evidence_span` forces the verdict to UNSUPPORTED regardless of what the model
claimed. LLMs are unreliable at consistently applying their own stated policy
(the same reasoning behind N7's deterministic arbitration) — a ten-line
regex check is more trustworthy than an instruction.
"""
from __future__ import annotations

import re

from veritas.clients import LLMResult, call_llm

MODEL = "gemini-3.6-flash"
TEMPERATURE = 0.0

PROMPT_TEMPLATE = """Answer ONE sub-claim using ONLY the evidence provided. Return ONLY JSON.

{{
  "claim_id": "{claim_id}",
  "verdict": "SUPPORTED" | "PARTIAL" | "UNSUPPORTED" | "CONTRADICTED",
  "answer": "<the answer, or null if not SUPPORTED/PARTIAL>",
  "evidence_span": "<VERBATIM sentence(s) from the evidence that establish this>",
  "source_url": "<url of the chunk the span came from>",
  "caveats": ["<conditions under which this answer does not hold>"]
}}

ABSOLUTE RULES:
- If the evidence does not contain the answer, verdict is UNSUPPORTED and
  answer is null. Do NOT use your own knowledge to fill the gap. Do NOT
  reason from general principles. Absence of evidence is a valid result.
- "evidence_span" must be copied verbatim from the evidence. If you cannot
  copy a span that establishes the claim, the verdict is not SUPPORTED.
- Numbers must appear literally in the evidence. Never compute, convert,
  interpolate, or round a value that is not stated.

CLAIM: {claim_question}
EVIDENCE:
{evidence_chunks_with_urls}
"""

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(_NUMBER_RE.findall(text))


def _enforce_numeric_grounding(data: dict) -> dict:
    """If a number in `answer` doesn't appear in `evidence_span`, force UNSUPPORTED."""
    answer_numbers = _numbers_in(data.get("answer"))
    span_numbers = _numbers_in(data.get("evidence_span"))
    unsupported_numbers = answer_numbers - span_numbers

    if unsupported_numbers and data.get("verdict") in ("SUPPORTED", "PARTIAL"):
        data = dict(data)
        data["verdict"] = "UNSUPPORTED"
        data["answer"] = None
        data.setdefault("caveats", [])
        data["caveats"] = list(data["caveats"]) + [
            f"code override: numeric value(s) {sorted(unsupported_numbers)} in the answer "
            f"were not found verbatim in evidence_span"
        ]
    return data


def _format_evidence(chunks: list) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[source: {c.url}]\n{c.text}")
    return "\n\n".join(parts) if parts else "(no evidence retrieved)"


def run(claim_id: str, claim_question: str, evidence_chunks: list) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(
        claim_id=claim_id,
        claim_question=claim_question,
        evidence_chunks_with_urls=_format_evidence(evidence_chunks),
    )
    result = call_llm("gemini", MODEL, prompt, temperature=TEMPERATURE, node="N5")
    result.data = _enforce_numeric_grounding(result.data)
    return result
