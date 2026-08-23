"""N2 — Risk Tier Gate. gemini-3.6-flash, temp 0.0."""
from veritas.clients import LLMResult, call_llm

MODEL = "gemini-3.6-flash"
TEMPERATURE = 0.0

PROMPT_TEMPLATE = """Classify the risk tier of a health/legal question. Return ONLY JSON.

TIER_0 — Emergency. Any indication of an in-progress medical emergency,
  self-harm, poisoning, severe bleeding, breathing difficulty, chest pain,
  stroke signs, or a child in acute distress.
  -> The system must STOP and escalate. No informational answer.

TIER_1 — High stakes. Answer errors could cause physical, legal, or financial
  harm: drug dosing, drug interactions, pregnancy, paediatrics, chronic disease
  management, legal deadlines, rights on arrest, contract obligations,
  pesticide application rates.
  -> Requires full grounding; refuse if evidence is insufficient.

TIER_2 — General information. Definitions, general processes, background.
  -> Grounded answer preferred; a clearly-labelled ungrounded answer is acceptable.

{{
  "tier": "TIER_0" | "TIER_1" | "TIER_2",
  "reasoning": "<one sentence>",
  "emergency_signals": ["<if TIER_0, the specific phrases that triggered it>"]
}}

Bias: when genuinely uncertain between two tiers, choose the HIGHER-risk tier.
An unnecessary escalation costs the user a minute. A missed one can cost more.

CANONICAL QUESTION: {canonical_english}
ORIGINAL: {original_question}
DOMAIN: {domain}
"""


def run(canonical_english: str, original_question: str, domain: str) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(
        canonical_english=canonical_english,
        original_question=original_question,
        domain=domain,
    )
    return call_llm("gemini", MODEL, prompt, temperature=TEMPERATURE, node="N2")
