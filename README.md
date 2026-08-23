# VERITAS
### Refusal-Aware Grounded Answering for Low-Resource Languages

> When you ask an LLM a high-stakes health or legal question in Nepali, it doesn't say "I don't know" — it invents a dosage. VERITAS is a nine-node workflow that decomposes the question into atomic claims, grounds each one in authoritative sources, has a second model actively try to falsify it, and **refuses to answer** when the evidence isn't there.

Built for Reverie Hacks 2026 — ML Prompt Engineering track.

---

## The comparison

| Failure mode | Single prompt | VERITAS |
|---|---|---|
| Nepali drug dosage question | Confidently states a number, no source, often wrong | Cites DDA/WHO or refuses |
| "What does Article X of the Labour Act say?" | Invents a plausible article number and content | Retrieves actual text or refuses |
| Romanized Nepali ("bukhar ko lagi k khane") | Misparses, answers a different question | Normalises to Devanagari, confirms intent |
| Medical emergency phrased casually | Gives home-remedy advice | Detects TIER-0, escalates, stops |
| Question with no good answer | Answers anyway | Explicit "unverified" section |

## Architecture

```mermaid
flowchart TD
    H[Human: question ne/en/romanized + domain] --> N1
    N1[N1 Language & Intent Normalizer<br/>gemini-2.0-flash] --> N2
    N2[N2 Risk Tier Gate<br/>gemini-2.0-flash] -->|TIER_1 / TIER_2| N3
    N2 -->|TIER_0 emergency| HALT[HALT: escalation card]
    N3[N3 Claim Decomposer<br/>gpt-oss:120b] --> N4
    N4[N4 Evidence Retrieval<br/>Firecrawl, whitelisted sources] --> N5
    N5[N5 Grounded Answerer per claim<br/>gemini-2.0-flash] --> N6
    N6[N6 Adversarial Verifier<br/>gpt-oss:120b, different family] --> N7
    N7[N7 Refusal Arbiter<br/>deterministic Python, no LLM] --> N8
    N8[N8 Synthesizer<br/>gemini-2.0-flash] --> N9
    N9[N9 Back-Translation Fidelity Check<br/>gemini-2.0-flash]
    N9 -->|drift detected, one retry| N8
    N9 --> OUT[Output: answer + citations + confidence + UNVERIFIED section]
    HALT --> OUT
```

Three design decisions that make this a *workflow* and not a chain:

1. **Cross-model verification (N6)** — the verifier (`gpt-oss:120b` via Ollama Cloud) is a different model family from the answerer (`gemini-2.0-flash`). A model asked to check its own work agrees with itself; a single prompt structurally cannot do this.
2. **Deterministic refusal arbitration (N7)** — the decision to refuse is made by Python, not an LLM. Refusal behaviour is auditable, testable, and identical every run.
3. **Atomic claim decomposition (N3)** — a compound question is split into independently-verifiable sub-claims, so partial knowledge produces a partial, honest answer instead of a single confident wrong one.

Full node-by-node reasoning: [docs/node_reference.md](docs/node_reference.md) · Design decisions: [docs/design_decisions.md](docs/design_decisions.md) · Comparison samples: [docs/samples.md](docs/samples.md)

## Quickstart

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # fill in GEMINI_API_KEY, OLLAMA_API_KEY, FIRECRAWL_API_KEY

python -m veritas.cli "बच्चालाई ज्वरो आयो, प्यारासिटामोल कति दिने?"

uvicorn server:app --reload   # live split-screen UI at http://localhost:8000
```

## Benchmark

30 questions, both arms, six metrics. See [benchmark/scorecard.md](benchmark/scorecard.md) once generated.

```bash
python benchmark/run_baseline.py
python benchmark/run_veritas.py
python benchmark/score.py
```

## Status

Work in progress — build phases tracked in commit history.
