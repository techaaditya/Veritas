"""N1 — Language & Intent Normalizer. gemini-2.0-flash, temp 0.1."""
from veritas.clients import LLMResult, call_llm

MODEL = "gemini-2.0-flash"
TEMPERATURE = 0.1

PROMPT_TEMPLATE = """You are a query normalizer for a Nepali/English health-and-legal information system.

INPUT: a user question that may be in Devanagari Nepali, romanized Nepali
(Nepali written in Latin script), English, or code-mixed.

Return ONLY a JSON object, no prose, no markdown fences:
{{
  "detected_language": "ne" | "en" | "ne-Latn" | "mixed",
  "devanagari_form": "<the question in Devanagari, or null if source is English>",
  "canonical_english": "<a precise English restatement of the question>",
  "domain": "health" | "legal" | "agriculture" | "other",
  "entities": ["<named drugs, laws, conditions, crops mentioned>"],
  "implicit_context": ["<facts the user assumed but did not state>"],
  "ambiguities": ["<anything genuinely unclear that changes the answer>"]
}}

Rules:
- Do NOT answer the question.
- If the question omits information that materially changes a safe answer
  (age, weight, pregnancy status, jurisdiction, date), list it in "ambiguities".
- Preserve the user's exact intent. Do not make the question safer or broader.

QUESTION: {user_question}
"""


def run(user_question: str) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(user_question=user_question)
    return call_llm("gemini", MODEL, prompt, temperature=TEMPERATURE, node="N1")
