"""N8 — Synthesizer. gemma4:31b via Ollama Cloud, temp 0.3."""
from veritas.clients import LLMResult, call_llm

MODEL = "gemma4:31b"
TEMPERATURE = 0.3

PROMPT_TEMPLATE = """Compose the final response in the user's original language ({detected_language}).

Structure, in this order:
1. The direct answer, built ONLY from claims with verdict SUPPORTED or PARTIAL.
2. Inline citation markers [1] [2] mapped to source URLs.
3. A section titled "यो कुरा पुष्टि गर्न सकिएन" / "Could not be verified"
   listing every UNSUPPORTED or CONTRADICTED claim in plain language.
   NEVER omit this section when such claims exist.
4. Any caveats from the claim caveats fields.
5. If arbiter_decision is REFUSE: do not answer at all. State plainly what
   could not be established and direct the user to a qualified professional.

Rules:
- Add NOTHING that is not in the supported claims. No helpful context, no
  general advice, no "additionally you should".
- Match the user's register. If they wrote informal romanized Nepali, reply
  in accessible Nepali, not bureaucratic Nepali.
- Do not soften a refusal into a hedged answer.

ARBITER DECISION: {decision}
CLAIMS: {claims_with_verdicts}

Return ONLY JSON:
{{
  "response_text": "<the full composed response in the user's language>",
  "citations": [{{"marker": "[1]", "url": "<source url>"}}]
}}
"""


def run(detected_language: str, decision: str, claims_with_verdicts: str, drift_note: str | None = None) -> LLMResult:
    prompt = PROMPT_TEMPLATE.format(
        detected_language=detected_language,
        decision=decision,
        claims_with_verdicts=claims_with_verdicts,
    )
    if drift_note:
        prompt += f"\n\nPREVIOUS ATTEMPT HAD FIDELITY DRIFT — FIX THIS:\n{drift_note}\n"
    return call_llm("ollama", MODEL, prompt, temperature=TEMPERATURE, node="N8")
