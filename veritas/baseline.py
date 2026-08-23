"""
The baseline arm — a single, scrupulously fair prompt. This is what VERITAS
is measured against. It even asks for uncertainty and citations, so beating
it is a real result, not a strawman comparison.
"""
from veritas.clients import RawResult, call_llm_raw, stream_ollama_raw

MODEL = "gemma4:31b"
TEMPERATURE = 0.7

PROMPT_TEMPLATE = """You are a helpful health and legal information assistant for users in Nepal.
Answer the user's question accurately. If you are not sure, say so.
Cite sources where possible.

QUESTION: {user_question}
"""


def run(user_question: str) -> RawResult:
    """Blocking call — used by the benchmark runner."""
    prompt = PROMPT_TEMPLATE.format(user_question=user_question)
    return call_llm_raw("ollama", MODEL, prompt, temperature=TEMPERATURE, node="baseline")


def run_stream(user_question: str):
    """Token-stream generator — used by the live web UI."""
    prompt = PROMPT_TEMPLATE.format(user_question=user_question)
    yield from stream_ollama_raw(MODEL, prompt, TEMPERATURE)
