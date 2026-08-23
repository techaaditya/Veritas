"""N3 — Claim Decomposer. gpt-oss:120b via Ollama Cloud, temp 0.2."""
from veritas.clients import LLMResult, call_llm

PROVIDER = "ollama"
MODEL = "gpt-oss:120b"
TEMPERATURE = 0.2
FALLBACK = ("featherless", "llama-3.3-70b")

PROMPT_TEMPLATE = """Decompose a question into atomic, independently verifiable sub-claims.

An atomic claim is one that a single authoritative source could confirm or
deny on its own. If a claim needs two different facts, split it.

Return ONLY JSON:
{{
  "claims": [
    {{
      "id": "C1",
      "claim_question": "<the sub-question, in English>",
      "claim_type": "factual" | "procedural" | "numeric" | "conditional",
      "criticality": "critical" | "supporting",
      "search_terms": ["<2-4 terms for retrieving evidence>"]
    }}
  ]
}}

Rules:
- Produce between 2 and 6 claims. Never one.
- Mark a claim "critical" if a wrong answer to it makes the whole response
  harmful, not merely incomplete.
- NUMERIC claims (doses, deadlines, thresholds, rates) are always "critical".
- Do NOT answer any claim.

QUESTION: {canonical_english}
ENTITIES: {entities}
DOMAIN: {domain}
"""


def run(canonical_english: str, entities: list[str], domain: str) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(
        canonical_english=canonical_english,
        entities=entities,
        domain=domain,
    )
    return call_llm(
        PROVIDER, MODEL, prompt, temperature=TEMPERATURE, node="N3", fallback=FALLBACK
    )
