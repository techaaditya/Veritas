# VERITAS: Node Reference

This document explains the reasoning behind each node, how it works, and the implementation detail that supports it. Every LLM node returns strict JSON so the orchestrator stays simple. The shared cache, retry, and telemetry layer that every node calls through lives in [veritas/clients.py](../veritas/clients.py).

Cost figures below use published per-million-token rates as a relative comparison, not as a billing statement. Actual dollar figures come from the benchmark's recorded telemetry in `benchmark/scorecard.md`.

---

## N1: Language and Intent Normalizer

**Purpose.** Without this node, every downstream prompt has to handle Devanagari, romanized Nepali, and code-mixed input on its own, and each one would handle it slightly differently. That inconsistency is exactly what this project exists to eliminate. Centralizing normalization means N2 onward can assume clean canonical English plus a Devanagari form for the final response.

**Model and parameters.** `gemma4:31b` via Ollama Cloud, temperature 0.1. Low but not zero. Normalization is close to deterministic, but a little flexibility helps with genuinely ambiguous romanized spelling. Gemma was chosen here for its strong multilingual grounding, including Devanagari.

**Prompt.** See [veritas/nodes/n1_normalize.py](../veritas/nodes/n1_normalize.py).

**I/O schema.** Input: raw user question (string). Output: `detected_language`, `devanagari_form`, `canonical_english`, `domain`, `entities`, `implicit_context`, `ambiguities`.

**Failure modes observed.** The prompt explicitly forbids the model from answering the question or from silently expanding scope ("do not make the question safer or broader"). Early drafts without that line risked N1 injecting its own interpretation of an ambiguous question, which would then travel through the whole pipeline as if it were the user's actual intent.

**Cost per call.** About $0.0001 to $0.0003 depending on question length. One call per run.

---

## N2: Risk Tier Gate

**Purpose.** Not every question deserves the same scrutiny. A definitional question ("what is a labour tribunal") does not need the same evidentiary bar as a paediatric dosing question, and an in-progress emergency needs the pipeline to get out of the way entirely rather than spend eight seconds retrieving evidence. This node routes those three cases differently before any expensive work happens.

**Model and parameters.** `gemma4:31b`, temperature 0.0. Classification should be as close to deterministic as an LLM gets. Temperature 0 minimizes tier-flapping across identical inputs.

**Prompt.** See [veritas/nodes/n2_risk_gate.py](../veritas/nodes/n2_risk_gate.py). It instructs the model to bias toward the higher-risk tier under genuine uncertainty. An unnecessary escalation costs a user a minute of reading an emergency card. A missed one can cost much more.

**I/O schema.** Input: canonical English question, original question, domain. Output: `tier`, `reasoning`, `emergency_signals`.

**Failure modes observed.** TIER-0 detection is the highest-stakes classification in the system, because a false negative here means the pipeline proceeds to give an informational answer during a real emergency. The bias-toward-higher-tier instruction is the direct mitigation, and TIER-0 escalation recall is tracked as one of the six benchmark metrics rather than folded into a general accuracy number.

**Cost per call.** About $0.0001 to $0.0002. One call per run, on the critical path for every downstream decision.

---

## N3: Claim Decomposer

**Purpose.** A compound question like "my 2-year-old has fever and I have paracetamol, how much do I give?" bundles several separately verifiable sub-facts: the correct drug class for paediatric fever, whether dosing is weight-based, the actual mg/kg figure, and the red-flag conditions that override home treatment. A single-prompt system answers the whole thing at once and hallucinates whichever sub-fact it is weakest on, silently, inside a confident-sounding paragraph. Decomposing first means each sub-claim gets its own evidence and its own verdict. A system with partial knowledge should produce a partial, honest answer, not a complete confident one.

**Model and parameters.** `gpt-oss:120b` via Ollama Cloud, temperature 0.2. This is a reasoning-heavy structuring task, not a factual-recall task, which is why it runs on the same model family used for N6 rather than the Gemma family used for N5, N8, and N9. See [design_decisions.md](design_decisions.md) for why keeping N5 and N6 on different families matters more than where N3 sits.

**Prompt.** See [veritas/nodes/n3_decompose.py](../veritas/nodes/n3_decompose.py). Numeric claims (doses, deadlines, thresholds, rates) are always forced to `critical`. A wrong number is never merely a supporting detail.

**I/O schema.** Input: canonical English question, entities, domain. Output: `claims[]`, each with `id`, `claim_question`, `claim_type`, `criticality`, `search_terms`.

**Failure modes observed.** The instruction to never return a single claim exists because early testing showed the model would sometimes treat an already-narrow question as one atomic claim, which defeats the purpose of decomposition for exactly the multi-part questions that need it most.

**Cost per call.** About $0.0002 to $0.0005. One call per run.

---

## N4: Evidence Retrieval

**Purpose.** This is not an LLM node. It is Firecrawl running a site-restricted search and scrape, constrained to the domains in [veritas/whitelist.py](../veritas/whitelist.py). The domain whitelist is a substantive design decision, not plumbing. VERITAS only ever grounds a claim in a source from a fixed, small, curated list of health, legal, and agriculture authorities. If a claim has zero whitelisted evidence, it is marked `NO_EVIDENCE` and passed forward honestly. VERITAS never falls back to open web search, because that would quietly reintroduce the exact unverified-source problem the whole pipeline exists to eliminate.

**Model.** None. Firecrawl API (`search` plus inline scrape via `scrape_options`).

**Implementation.** See [veritas/nodes/n4_retrieve.py](../veritas/nodes/n4_retrieve.py). Every retrieval is cached to disk by `(claim_question, domain)`. On a Firecrawl outage, a missing key, or zero whitelisted results, it falls back to a small hand-curated local corpus in [corpus/](../corpus/) of real, verbatim, source-attributed extracts. This keeps the pipeline demoable and testable even without live API access, and every fallback is stamped `degraded=True` with a reason rather than silently substituted.

**Failure modes observed.** Two are worth naming. First, `corpus/agriculture.json` is currently empty. During authoring there was not time to hand-verify agriculture sources to the same standard as health and legal, so agriculture claims depend entirely on live Firecrawl access. That is reported as a finding about source availability by domain rather than papered over with unverified placeholder text. Second, some authoritative medical hosts (for example NCBI and PMC) return a bot check instead of article content to automated requests. When that happens the answerer is starved of evidence it would otherwise have grounded on, and the claim ends up refused. That is a retrieval limitation, not a reasoning one, and the direct fix is a wider whitelist plus cached full-text copies of key clinical references.

**Cost per call.** Firecrawl usage against the participant credit allocation. Not an LLM cost.

---

## N5: Grounded Answerer

**Purpose.** Answers exactly one claim, using only the evidence retrieved for it. This is the node most directly responsible for suppressing hallucination. It is forbidden from using the model's own world knowledge, forbidden from reasoning from general principles, and required to copy a verbatim `evidence_span` as proof of grounding.

**Model and parameters.** `gemma4:31b`, temperature 0.0. Zero temperature because this is an extraction task, not a generative one. Any creativity here shows up as fabrication.

**Prompt.** See [veritas/nodes/n5_answer.py](../veritas/nodes/n5_answer.py).

**Code-level enforcement.** Beyond the prompt's own instruction, [n5_answer.py](../veritas/nodes/n5_answer.py) enforces numeric grounding in Python. Every number in `answer` is checked against `evidence_span`, and if any number is not present verbatim, the verdict is overridden to `UNSUPPORTED` regardless of what the model claimed. This mirrors N7's philosophy: LLMs are unreliable at consistently applying their own stated policy, so the policy that matters most is enforced in code, not prose.

**I/O schema.** Input: claim question, evidence chunks. Output: `claim_id`, `verdict`, `answer`, `evidence_span`, `source_url`, `caveats`.

**Failure modes observed.** Without the code-level numeric check, a likely failure is the model copying a real evidence span but then helpfully converting or rounding a number in the `answer` field, for example turning a per-dose figure into a daily total. It looks grounded because the span is real, but the number in the answer was never in the evidence. The Python check catches this class of error no matter how the prompt is phrased.

**Cost per call.** About $0.0001 to $0.0003 per claim. Up to six claims per run, run concurrently.

---

## N6: Adversarial Verifier

**Purpose.** A model asked to check its own work agrees with itself far more often than it should. This is a well-documented shared-prior failure. N6 breaks it by routing the falsification attempt through a genuinely different model family.

**Model and parameters.** `gpt-oss:120b` via Ollama Cloud, temperature 0.3. This is deliberately a different family from N5's Gemma. gpt-oss (OpenAI lineage, mixture-of-experts) and Gemma (Google, open-weight dense) share no training lineage, even though both are reached through the same Ollama Cloud API. That is a stronger separation than routing both through two checkpoints of one vendor's model family. A single prompt has no mechanism to do this at all, and a chain that self-checks with the same model is only marginally better.

**Prompt.** See [veritas/nodes/n6_verify.py](../veritas/nodes/n6_verify.py). It is framed as hostile: "assume the answerer made a mistake and find it." It also tells the model not to manufacture objections when it genuinely cannot find one. An adversarial framing that always finds something wrong is exactly as useless as one that never does.

**I/O schema.** Input: claim question, proposed answer, evidence span, source URL. Output: `falsification_attempt`, `flags[]`, `verdict_after_challenge`, `confidence`.

**Failure modes observed.** `NUMBER_MISMATCH` and `SCOPE_DROPPED` are the two flags that most directly feed N7's refusal logic. During development the most common genuine catch was scope-dropping: an adult dosing figure presented by N5 without carrying forward a population caveat that was present in the source evidence.

**Cost per call.** About $0.0002 to $0.0006 per claim. Runs for every claim that has an `evidence_span`, and is skipped for `NO_EVIDENCE` claims from N4 since there is nothing to falsify.

---

## N7: Refusal Arbiter

**Purpose.** The decision to refuse is the most safety-critical output of the whole system, and it is made by Python, not an LLM. LLMs are unreliable at consistently applying their own refusal policy. Ask the same model the same borderline question twice and it will not always refuse the same way. Moving the decision into code makes refusal behaviour auditable line by line, testable in isolation, and identical on every run given the same claim verdicts.

**Model.** None. Pure deterministic Python.

**Implementation.** See [veritas/nodes/n7_arbiter.py](../veritas/nodes/n7_arbiter.py), fully covered by [tests/test_arbiter.py](../tests/test_arbiter.py) with 15 unit tests across every decision branch, including the empty-claims and supporting-only-failure edge cases.

**I/O schema.** Input: risk tier, list of claim verdicts plus adversarial challenge results. Output: `decision` (`ANSWER`, `PARTIAL_ANSWER`, or `REFUSE`) and `reasons[]`.

**Failure modes observed.** None in the sense that matters, which is the point. The only risk worth naming is a design risk: if a future contributor is tempted to route this decision back through an LLM for flexibility, that would quietly reintroduce the exact inconsistency problem N7 exists to solve. This file should stay boring.

**Cost per call.** Zero. This is the cheapest and most important node in the system.

---

## N8: Synthesizer

**Purpose.** Composes the final response in the user's own language, built strictly from claims with verdict `SUPPORTED` or `PARTIAL`. Anything not in the verified claim set is forbidden. No "additionally you should," no helpful general context, because that is exactly the kind of ungrounded addition that reintroduces hallucination one layer downstream of where the rest of the pipeline was fighting it.

**Model and parameters.** `gemma4:31b`, temperature 0.3. This is the only generative node with meaningfully above-zero temperature, because natural, register-appropriate Nepali phrasing benefits from it, and the content it is allowed to draw from is already fully constrained.

**Prompt.** See [veritas/nodes/n8_synthesize.py](../veritas/nodes/n8_synthesize.py). It requires an explicit "Could not be verified" section whenever unsupported claims exist, and forbids softening a `REFUSE` decision into a hedged answer.

**I/O schema.** Input: detected language, arbiter decision, claims with verdicts, and an optional drift note on retry. Output: `response_text`, `citations[]`.

**Failure modes observed.** Register mismatch. A first draft of this prompt produced grammatically correct but bureaucratic Nepali in response to casual romanized input. The rule to match the user's register was added directly in response to that gap.

**Cost per call.** About $0.0003 to $0.0008. One call per run, plus one retry call if N9 detects fidelity drift.

---

## N9: Back-Translation Fidelity Check

**Purpose.** Translation is where safety guarantees quietly die. A pipeline can verify every claim perfectly in English and then produce a Nepali sentence that drops the word "not." Almost no comparable system checks this, because it requires a second independent verification pass after the content is already believed to be finished.

**Model and parameters.** `gemma4:31b`, temperature 0.0. Literal back-translation, not creative restatement.

**Prompt.** See [veritas/nodes/n9_fidelity.py](../veritas/nodes/n9_fidelity.py). `fidelity_ok` is forced false on any high-severity drift, with three named danger cases: a changed number, a vanished caveat, or a refusal that became an answer in translation.

**Control flow.** On `fidelity_ok: false`, the orchestrator retries N8 once with the drift report appended, then re-runs N9. If it still fails, the pipeline degrades to a bilingual side-by-side response (the translated text plus the verified English claim summary) rather than silently shipping a drifted answer. See [veritas/orchestrator.py](../veritas/orchestrator.py).

**I/O schema.** Input: final response text, verified claims. Output: `back_translation`, `drift[]`, `fidelity_ok`.

**Failure modes observed.** This node exists precisely because its failure mode is invisible without it. By construction, a hallucination introduced in translation looks identical to a correct answer to anyone who does not independently re-check the English. Having no incident to report is itself the argument for keeping the check in the pipeline permanently rather than treating it as optional.

**Cost per call.** About $0.0002 to $0.0004. One call per run, plus one retry call on drift, capped at one retry.
