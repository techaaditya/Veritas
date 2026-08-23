"""
N9 — Back-Translation Fidelity Check. gemini-2.5-flash, temp 0.0.

Translation is where safety guarantees quietly die. A pipeline can verify
everything perfectly in English and then produce a Nepali sentence that
drops the word "not." Almost nobody checks this.
"""
from veritas.clients import LLMResult, call_llm

MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.0

PROMPT_TEMPLATE = """Translate the Nepali response below back into English, literally.
Then compare it against the verified claim set.

Return ONLY JSON:
{{
  "back_translation": "<literal English>",
  "drift": [
    {{"type": "ADDED" | "DROPPED" | "ALTERED",
     "detail": "<what changed>",
     "severity": "high" | "low"}}
  ],
  "fidelity_ok": true | false
}}

fidelity_ok is false if ANY high-severity drift exists, especially:
a number that changed, a caveat that vanished, or a refusal that became
an answer in translation.

NEPALI RESPONSE: {final_response}
VERIFIED CLAIMS: {claims_with_verdicts}
"""


def run(final_response: str, claims_with_verdicts: str) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(
        final_response=final_response,
        claims_with_verdicts=claims_with_verdicts,
    )
    return call_llm("gemini", MODEL, prompt, temperature=TEMPERATURE, node="N9")
