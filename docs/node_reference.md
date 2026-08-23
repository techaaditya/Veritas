# VERITAS — Node Reference

Reasoning behind each node, how it works, and supporting implementation detail. Every LLM node returns strict JSON so the orchestrator stays simple — see [veritas/clients.py](../veritas/clients.py) for the shared cache/retry/telemetry layer every node calls through.

Cost figures below use published per-1M-token rates as a relative comparison, not billing; actual dollars come from the benchmark's recorded telemetry (`benchmark/scorecard.md` once generated).

---

## N1 — Language & Intent Normalizer

**Purpose.** Without this node, every downstream prompt has to individually handle Devanagari, romanized Nepali, and code-mixed input — and every one of them will handle it slightly differently, which is exactly the kind of inconsistency this project exists to eliminate. Centralizing normalization means N2 onward can assume clean, canonical English plus a Devanagari form for the final response.

**Model & parameters.** `gemma4:31b` via Ollama Cloud, temperature 0.1. Low but non-zero — normalization is close to deterministic, but a touch of flexibility helps with genuinely ambiguous romanized spelling. Gemma was chosen here for its strong multilingual grounding, including Devanagari.

**Prompt.** See [veritas/nodes/n1_normalize.py](../veritas/nodes/n1_normalize.py).

**I/O schema.** Input: raw user question (string). Output: `detected_language`, `devanagari_form`, `canonical_english`, `domain`, `entities`, `implicit_context`, `ambiguities`.

**Failure modes observed.** The prompt explicitly forbids the model from answering the question or from silently expanding scope ("do not make the question safer or broader") — early drafts without that line risked N1 injecting its own interpretation of ambiguous questions, which would then propagate through the whole pipeline as if it were user intent.

**Cost per call.** ~$0.0001–0.0003 depending on question length; single call per run.

---

## N2 — Risk Tier Gate

**Purpose.** Not every question deserves the same scrutiny. A definitional question ("what is a labour tribunal") doesn't need the same evidentiary bar as a paediatric dosing question, and an in-progress emergency needs the pipeline to get out of the way entirely rather than spend 8 seconds retrieving evidence. This node exists to route those three cases differently before any expensive work happens.

**Model & parameters.** `gemma4:31b`, temperature 0.0. Classification should be as close to deterministic as an LLM gets; temperature 0 minimizes tier-flapping across identical inputs.

**Prompt.** See [veritas/nodes/n2_risk_gate.py](../veritas/nodes/n2_risk_gate.py). Notably instructs the model to bias toward the *higher*-risk tier under genuine uncertainty — an unnecessary escalation costs a user a minute of reading an emergency card; a missed one can cost more.

**I/O schema.** Input: canonical English question, original question, domain. Output: `tier`, `reasoning`, `emergency_signals`.

**Failure modes observed.** TIER_0 detection is the single highest-stakes classification in the system, since a false negative here means the pipeline proceeds to give an informational answer during a real emergency. The bias-toward-higher-tier instruction is a direct mitigation, and TIER_0 escalation recall is tracked explicitly as one of the six benchmark metrics rather than folded into a general accuracy number.

**Cost per call.** ~$0.0001–0.0002; single call per run, on the critical path for every downstream decision.

---

## N3 — Claim Decomposer

**Purpose.** A compound question like "my 2-year-old has fever and I have paracetamol, how much do I give?" bundles several separately-verifiable sub-facts (correct drug class for paediatric fever, weight-basis of dosing, the actual mg/kg figure, red-flag conditions). A single-prompt system answers the gestalt and hallucinates whichever sub-fact it's weakest on, silently, inside a confident-sounding paragraph. Decomposing first means each sub-claim gets its own evidence and its own verdict — a system with partial knowledge should produce a partial, honest answer, not a complete confident one.

**Model & parameters.** `gpt-oss:120b` via Ollama Cloud, temperature 0.2. This is a reasoning-heavy structuring task, not a factual-recall task, which is why it's routed to the same model family used for N6 rather than the Gemma family used for N5, N8, N9 — see [design_decisions.md](design_decisions.md) for why keeping N3 and N5 on different families matters less than keeping N5 and N6 on different families.

**Prompt.** See [veritas/nodes/n3_decompose.py](../veritas/nodes/n3_decompose.py). Numeric claims (doses, deadlines, thresholds, rates) are always forced `critical` — a wrong number is never merely "supporting" detail.

**I/O schema.** Input: canonical English question, entities, domain. Output: `claims[]`, each with `id`, `claim_question`, `claim_type`, `criticality`, `search_terms`.

**Failure modes observed.** The instruction "never one" claim exists because early testing showed the model would sometimes treat an already-narrow question as a single atomic claim, which defeats the point of decomposition for exactly the multi-part questions that need it most.

**Cost per call.** ~$0.0002–0.0005; single call per run.

---

## N4 — Evidence Retrieval

**Purpose.** This is not an LLM node — it's Firecrawl doing a site-restricted search and scrape, constrained to [veritas/whitelist.py](../veritas/whitelist.py). The domain whitelist is a substantive design decision, not plumbing: VERITAS only ever grounds claims in sources from a fixed, small, curated list of health/legal/agriculture authorities. If a claim has zero whitelisted evidence, it is marked `NO_EVIDENCE` and passed forward honestly. **VERITAS never falls back to open web search** — that would silently reintroduce the exact unverified-source problem the whole pipeline exists to eliminate.

**Model.** N/A — Firecrawl API (`search` + inline scrape via `scrape_options`).

**Implementation.** See [veritas/nodes/n4_retrieve.py](../veritas/nodes/n4_retrieve.py). Every retrieval is cached to disk by `(claim_question, domain)`. On a Firecrawl outage, missing key, or zero whitelisted results, it falls back to a small hand-curated local corpus ([corpus/](../corpus/)) of real, verbatim, source-attributed extracts — this keeps the pipeline demoable and testable even without live API access, and every fallback is stamped `degraded=True` with a reason, never silently substituted.

**Failure modes observed.** The `corpus/agriculture.json` bucket is currently empty — during authoring there wasn't time to hand-verify agriculture-domain sources to the same standard as health/legal, so agriculture claims depend entirely on live Firecrawl access. This is reported honestly rather than papered over with unverified placeholder content: sparse source availability by domain is a finding, not a bug, and the benchmark scorecard reports it as such.

**Cost per call.** Firecrawl usage against the 10,000-credit participant allocation; not an LLM cost.

---

## N5 — Grounded Answerer

**Purpose.** Answers exactly one claim, using only the evidence retrieved for it. This is the node most directly responsible for suppressing hallucination: it is explicitly forbidden from using the model's own world knowledge, forbidden from reasoning "from general principles," and required to copy a verbatim `evidence_span` as proof of grounding.

**Model & parameters.** `gemma4:31b`, temperature 0.0. Zero temperature because this is an extraction task, not a generative one — any creativity here manifests as fabrication.

**Prompt.** See [veritas/nodes/n5_answer.py](../veritas/nodes/n5_answer.py).

**Code-level enforcement.** Beyond the prompt's own instruction, [n5_answer.py](../veritas/nodes/n5_answer.py) enforces numeric grounding in Python: every number appearing in `answer` is checked against `evidence_span`, and if any number doesn't appear verbatim, the verdict is force-overridden to `UNSUPPORTED` regardless of what the model claimed. This mirrors N7's philosophy — LLMs are unreliable at consistently applying their own stated policy, so the policy that matters most is enforced in code, not prose.

**I/O schema.** Input: claim question, evidence chunks. Output: `claim_id`, `verdict`, `answer`, `evidence_span`, `source_url`, `caveats`.

**Failure modes observed.** Without the code-level numeric check, a plausible failure mode is the model correctly copying an evidence span but then "helpfully" converting or rounding a number in the `answer` field (e.g. converting a per-dose figure into a daily total) — which looks grounded because the span is real, but the number in the answer wasn't in the evidence. The regex check catches this class of error regardless of how the prompt is phrased.

**Cost per call.** ~$0.0001–0.0003 per claim; up to 6 claims per run (2–6 per N3's decomposition), run concurrently.

---

## N6 — Adversarial Verifier

**Purpose.** A model asked to check its own work agrees with itself far more often than it should — a well-documented shared-prior failure. N6 exists to break that by routing the falsification attempt through a genuinely different model family.

**Model & parameters.** `gpt-oss:120b` via Ollama Cloud, temperature 0.3. **Deliberately a different family from N5's Gemma** — gpt-oss (OpenAI-lineage, mixture-of-experts) and Gemma (Google, open-weight dense) share no training lineage, even though both are reached through the same Ollama Cloud API. That's a stronger separation than routing both through two checkpoints of the same vendor's model family. A single prompt has no mechanism to do this at all; a chain that self-checks with the same model is only marginally better.

**Prompt.** See [veritas/nodes/n6_verify.py](../veritas/nodes/n6_verify.py). Framed explicitly as hostile: "assume the answerer made a mistake and find it." The prompt also instructs the model not to manufacture objections when it genuinely can't find one — an adversarial framing that always finds *something* wrong is exactly as useless as one that never does.

**I/O schema.** Input: claim question, proposed answer, evidence span, source URL. Output: `falsification_attempt`, `flags[]`, `verdict_after_challenge`, `confidence`.

**Failure modes observed.** `NUMBER_MISMATCH` and `SCOPE_DROPPED` are the two flags that most directly feed N7's refusal logic; during development, the most common genuine catch here was scope-dropping — an adult dosing figure presented by N5 without carrying forward a population caveat that was present in the source evidence.

**Cost per call.** ~$0.0002–0.0006 per claim; runs for every claim that has an `evidence_span` (skipped for claims that were `NO_EVIDENCE` from N4, since there's nothing to falsify).

---

## N7 — Refusal Arbiter

**Purpose.** The decision to refuse is the single most safety-critical output of the whole system, and it is made by Python, not an LLM. LLMs are unreliable at consistently applying their own stated refusal policy — ask the same model the same borderline question twice and it will not always refuse the same way. Moving the decision into code makes refusal behaviour auditable line-by-line, testable in isolation, and byte-for-byte identical on every run given the same claim verdicts.

**Model.** None — pure deterministic Python.

**Implementation.** See [veritas/nodes/n7_arbiter.py](../veritas/nodes/n7_arbiter.py), fully covered by [tests/test_arbiter.py](../tests/test_arbiter.py) (15 unit tests across every decision branch, including the empty-claims and supporting-only-failure edge cases).

**I/O schema.** Input: risk tier, list of claim verdicts + adversarial challenge results. Output: `decision` (`ANSWER` / `PARTIAL_ANSWER` / `REFUSE`), `reasons[]`.

**Failure modes observed.** None in the sense that matters — that's the point. The only "failure mode" worth naming is a *design* risk: if a future contributor is tempted to route this decision back through an LLM for flexibility, that would silently reintroduce the exact inconsistency problem N7 exists to solve. This file should stay boring.

**Cost per call.** $0. This is the cheapest and most important node in the system.

---

## N8 — Synthesizer

**Purpose.** Composes the final response in the user's own language, built strictly from claims with verdict `SUPPORTED` or `PARTIAL`. Everything not in the verified claim set is explicitly forbidden — no "additionally you should," no helpful general context, because that's exactly the kind of ungrounded addition that reintroduces hallucination one layer downstream of where the rest of the pipeline was fighting it.

**Model & parameters.** `gemma4:31b`, temperature 0.3 — the only generative node in the pipeline with meaningfully above-zero temperature, because natural, register-appropriate Nepali phrasing benefits from it, and the content it's allowed to draw from is already fully constrained.

**Prompt.** See [veritas/nodes/n8_synthesize.py](../veritas/nodes/n8_synthesize.py). Requires an explicit "Could not be verified" section whenever unsupported claims exist, and forbids softening a `REFUSE` decision into a hedged answer.

**I/O schema.** Input: detected language, arbiter decision, claims with verdicts (+ optional drift note on retry). Output: `response_text`, `citations[]`.

**Failure modes observed.** Register mismatch: a first draft of this prompt produced grammatically correct but bureaucratic-register Nepali in response to casual romanized input. The rule "match the user's register" was added directly in response to that gap.

**Cost per call.** ~$0.0003–0.0008; one call per run, plus one retry call if N9 detects fidelity drift.

---

## N9 — Back-Translation Fidelity Check

**Purpose.** Translation is where safety guarantees quietly die. A pipeline can verify every claim perfectly in English and then produce a Nepali sentence that drops the word "not." Almost no comparable system checks this, because it requires a second, independent verification pass *after* the content is already believed to be finished.

**Model & parameters.** `gemma4:31b`, temperature 0.0 — literal back-translation, not creative restatement.

**Prompt.** See [veritas/nodes/n9_fidelity.py](../veritas/nodes/n9_fidelity.py). `fidelity_ok` is forced false on any high-severity drift, with three named danger cases: a changed number, a vanished caveat, or a refusal that became an answer in translation.

**Control flow.** On `fidelity_ok: false`, the orchestrator retries N8 once with the drift report appended to the prompt, then re-runs N9. If it still fails, the pipeline degrades to a bilingual side-by-side response (translated text plus the verified English claim summary) rather than silently shipping a drifted answer — see [veritas/orchestrator.py](../veritas/orchestrator.py).

**I/O schema.** Input: final response text, verified claims. Output: `back_translation`, `drift[]`, `fidelity_ok`.

**Failure modes observed.** This node exists precisely because its failure mode is invisible without it — by construction, a hallucination-in-translation looks identical to a correct answer to anyone who doesn't independently re-check the English. No incident to report yet is itself evidence for why the check stays in the pipeline permanently rather than being treated as optional.

**Cost per call.** ~$0.0002–0.0004; one call per run, plus one retry call on drift (capped at one retry — see [design_decisions.md](design_decisions.md)).
