"""
N6 — Adversarial Verifier. gpt-oss:120b via Ollama Cloud, temp 0.3.

Deliberately a different model family from N5 (gemini-3.6-flash). A model
asked to check its own work agrees with itself far too often (shared-prior
failure); routing the falsification attempt through an unrelated model
family (OpenAI's gpt-oss vs. Google's Gemini, no shared training lineage)
breaks that failure mode in a way a single prompt structurally cannot.
"""
from veritas.clients import LLMResult, call_llm

PROVIDER = "ollama"
MODEL = "gpt-oss:120b"
TEMPERATURE = 0.3
FALLBACK = ("featherless", "llama-3.3-70b")

PROMPT_TEMPLATE = """You are a hostile fact-checker. Your job is to FALSIFY the claim below,
not to confirm it. Assume the answerer made a mistake and find it.

Check specifically for:
1. Does the evidence_span actually establish the answer, or merely relate to it?
2. Is any number in the answer absent from, or different in, the evidence span?
3. Has a condition, population, or jurisdiction limit been dropped?
   (e.g. adult dose presented as if universal; a rule that applies only to
   one province presented as national)
4. Is the source authoritative for THIS claim, or merely a reputable site
   that happens to mention it?
5. Is the evidence stale in a way that matters?

Return ONLY JSON:
{{
  "claim_id": "{claim_id}",
  "falsification_attempt": "<your strongest argument that this is wrong>",
  "flags": ["NUMBER_MISMATCH" | "SPAN_DOES_NOT_ESTABLISH" |
            "SCOPE_DROPPED" | "SOURCE_INAPPROPRIATE" | "STALE" | "NONE"],
  "verdict_after_challenge": "HOLDS" | "WEAKENED" | "FAILS",
  "confidence": 0.0-1.0
}}

If after genuine effort you cannot falsify it, say so — return flags ["NONE"]
and verdict "HOLDS". Do not manufacture objections.

CLAIM: {claim_question}
PROPOSED ANSWER: {answer}
EVIDENCE SPAN: {evidence_span}
SOURCE: {source_url}
"""


def run(claim_id: str, claim_question: str, answer: str | None, evidence_span: str | None, source_url: str | None) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(
        claim_id=claim_id,
        claim_question=claim_question,
        answer=answer or "(none — claim was UNSUPPORTED)",
        evidence_span=evidence_span or "(none)",
        source_url=source_url or "(none)",
    )
    return call_llm(
        PROVIDER, MODEL, prompt, temperature=TEMPERATURE, node="N6", fallback=FALLBACK
    )
