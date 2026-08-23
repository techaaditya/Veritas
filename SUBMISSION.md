# VERITAS — Devpost Submission Package

Reverie Hacks 2026 · ML Prompt Engineering track

---

## Tagline

*An LLM that says "I don't know" — a nine-node workflow that refuses rather than hallucinates on high-stakes Nepali health and legal questions.*

## Inspiration

Ask any frontier model a paediatric dosing question in Nepali and it will give you a number. It will not tell you it has no source for that number. For roughly 30 million Nepali speakers, "confidently wrong in your own language" is worse than no answer at all — and it's exactly the failure mode a single prompt has no structural way to prevent, because nothing forces it to admit the gap between what it knows and what it's asserting.

## What it does

VERITAS takes a health or legal question in Nepali, romanized Nepali, or English, and answers it the way a careful clinician or lawyer would: it breaks the question into its atomic factual claims, looks each one up against a fixed whitelist of authoritative sources (WHO, DDA, MOHP, the Nepal Law Commission, FAO), has a *second, unrelated model* try to falsify each answer, and only then lets a deterministic rule — not another LLM guess — decide whether to answer, partially answer, or refuse outright. If the question describes a medical emergency, the pipeline doesn't try to help informationally at all; it halts and shows an escalation card.

Nine nodes, nine distinct jobs:

1. **N1** normalizes language and intent (`gemini-2.0-flash`)
2. **N2** gates risk tier — TIER_0 emergencies halt the pipeline entirely (`gemini-2.0-flash`)
3. **N3** decomposes the question into 2–6 atomic claims (`gpt-oss:120b`, Ollama Cloud)
4. **N4** retrieves evidence only from a whitelisted domain list (Firecrawl, not an LLM)
5. **N5** answers each claim from evidence alone, with numeric grounding enforced in code (`gemini-2.0-flash`)
6. **N6** — a *different model family* — tries to falsify each answer (`gpt-oss:120b`, Ollama Cloud)
7. **N7** makes the ANSWER / PARTIAL_ANSWER / REFUSE decision deterministically, in plain Python, unit-tested
8. **N8** synthesizes the final response in the user's own language (`gemini-2.0-flash`)
9. **N9** back-translates the response to catch drift that only appears in translation, retrying once (`gemini-2.0-flash`)

## How we built it

Python 3.13, no orchestration framework — nine nodes don't need one, and hand-rolled orchestration is easier to audit and explain than a framework's implicit control flow. Every LLM call is cached to disk by prompt hash so the 30-question benchmark can be rerun without burning quota. Every node's raw input and output is logged to `logs/<run_id>.json` — those logs are themselves documentation evidence, not just debug output.

The live demo is a FastAPI backend streaming both arms — the single-prompt baseline and the full VERITAS pipeline — over Server-Sent Events to a from-scratch frontend ("The Tribunal"): a node-by-node trace, claim cards that visibly die when a claim fails verification, a physical-stamp-style REFUSE/ANSWER/PARTIAL_ANSWER arbiter decision, and a full-screen red takeover for TIER-0 emergencies.

Cross-model verification runs on Ollama Cloud's hosted `gpt-oss:120b` rather than the same vendor's model family used for the rest of the pipeline (Gemini) — OpenAI-lineage gpt-oss and Google's Gemini share no training lineage, which makes "the verifier can't just agree with itself" a real structural property of the system rather than a hopeful assumption.

## Challenges we ran into

- **Firecrawl outages can't take down the submission.** Evidence retrieval falls back to a small hand-curated local corpus of real, verbatim, source-attributed extracts whenever Firecrawl is unavailable or returns nothing — stamped `degraded=True` with a reason, never silently substituted.
- **Numbers are the easiest thing to get subtly wrong.** N5's prompt already forbids inventing or converting numbers, but LLMs are unreliable at consistently applying their own stated policy — so numeric grounding is enforced a second time in plain Python: any number in an answer that doesn't appear verbatim in the cited evidence forces the verdict to UNSUPPORTED, regardless of what the model claimed.
- **Translation is where safety guarantees quietly die.** A pipeline can verify every claim perfectly in English and still produce a Nepali sentence that drops the word "not" — invisible unless something specifically checks for it, which is the entire reason N9 exists.

## Accomplishments we're proud of

- A **real eval harness** — 30 questions across seven buckets, both arms run and scored on six separate metrics, with citation validity checked by live HTTP requests rather than assumed.
- **15 unit tests** covering every branch of the refusal arbiter — the most safety-critical decision in the system is also the most rigorously tested piece of code in it.
- Reporting **where we lose**, not just where we win: over-refusal rate and the real cost/latency multiple are first-class metrics in the scorecard, not footnotes.
- A demo interface that makes the workflow's control flow — the TIER-0 halt, the claims that die under adversarial challenge, the arbiter's stamped decision — visible and legible in real time, not just a chat box with a spinner.

## What we learned

That the hardest part of building a system to prevent hallucination isn't the grounding step — it's every *other* step that can quietly undo it. A perfectly grounded answer in English can still fail if the final translation drops a caveat, or if a Python bug lets a fabricated number through, or if the refusal policy is one more LLM call away from being applied inconsistently. Reliability here comes from treating every hand-off between steps as a place something can go wrong, not from making any single step smarter.

## What's next

Expand source coverage to Maithili and Bhojpuri, close the agriculture-domain evidence gap in the offline corpus, run the N6-disabled ablation to quantify what adversarial verification is actually buying, and package the pipeline as an API usable by frontline health workers — directly reusable groundwork for refusal-aware guardrails work beyond this hackathon.

## Built with

`python` `fastapi` `gemini-api` `gpt-oss` `ollama-cloud` `firecrawl` `prompt-engineering` `nlp` `low-resource-languages` `ai-safety` `server-sent-events`

---

## Demo video shot list (~3 minutes)

| Time | Content |
|---|---|
| 0:00–0:20 | Cold open, no intro. Screen split. Type the same Nepali dosing question into both arms live in the web UI. Baseline streams a confident number. VERITAS refuses and names which claim it couldn't verify. Say only: *"Same question. One of these made up a dose for a two-year-old."* |
| 0:20–0:50 | Explain what was built and why refusal is the feature, not a failure mode. |
| 0:50–1:50 | Walk the node spine live. Spend the most time on N6 (different model family, told to falsify) and N7 (refusal is code, not vibes — show the unit tests). |
| 1:50–2:30 | The scorecard tab. Read the numbers, including the ones where VERITAS loses (cost, latency, over-refusal). |
| 2:30–2:50 | TIER-0 demo — emergency phrasing, full-screen red halt, pipeline stops before attempting an informational answer. |
| 2:50–3:00 | One line on what's next: Maithili/Bhojpuri, an API for health workers. |

Record with OBS, one dry run, no more than three takes.

## Submission checklist

- [ ] Repo is public with `LICENSE` (MIT) present
- [ ] `.env` filled in locally with real API keys (not committed — see `.env.example`)
- [ ] `python benchmark/run_baseline.py && python benchmark/run_veritas.py && python benchmark/score.py` run to completion
- [ ] `python docs/build_samples.py` run so `docs/samples.md` has real deep-dive output
- [ ] `docs/workflow.png` uploaded as the workflow diagram deliverable
- [ ] `docs/samples.md` (or a PDF export of it) uploaded as the Samples deliverable
- [ ] `docs/node_reference.md` + `docs/design_decisions.md` uploaded as the Documentation deliverable
- [ ] Demo video recorded, uploaded to YouTube **unlisted** (not private), link added here
- [ ] Devpost fields filled from the sections above
- [ ] Submission confirmation screenshotted
