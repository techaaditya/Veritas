# VERITAS — Design Decisions

Five decisions carry the whole argument for why this is a *workflow* and not a single clever prompt. Each is presented as: the naive approach, why it fails, and what VERITAS does instead.

---

## 1. Deterministic refusal arbitration

**Naive approach.** Ask the LLM, as part of its answer-generation prompt, to decide for itself whether it has enough evidence to answer, and to refuse if not.

**Why it fails.** LLMs are unreliable at consistently applying their own stated policy. The same model, given the same borderline evidence, will not refuse identically across two runs — refusal becomes a matter of sampling noise on the exact question where consistency matters most. It's also unauditable: there's no way to point at a line of a prompt and say "this is why it refused," because the actual decision boundary lives somewhere inside the model's weights, shaped by the temperature and phrasing of that particular call.

**What VERITAS does instead.** The refusal decision is made by [`veritas/nodes/n7_arbiter.py`](node_reference.md#n7--refusal-arbiter) — plain Python, no LLM call, fully covered by unit tests. Given the same tier and the same claim verdicts, it produces the same decision every time, and every branch of its logic is testable and readable in isolation. This is the single most defensible design choice in the system: it converts "we asked the model to be careful" into "we wrote down the rule and tested it."

---

## 2. Cross-model adversarial verification

**Naive approach.** Have the same model check its own answer — either in the same completion ("are you sure?") or a second call with a "critic" persona.

**Why it fails.** A model checking its own work shares the same training-induced blind spots, the same confident-but-wrong priors, and often the same specific error, as the model that produced the answer in the first place. This is a well-documented failure mode: self-critique tends to rubber-stamp rather than genuinely falsify, especially on the exact class of question where the model was already confidently wrong.

**What VERITAS does instead.** N5 (the answerer) runs on `gemini-2.5-flash`; N6 (the verifier) runs on `gpt-oss:120b` via Ollama Cloud — a genuinely different model family with no shared training lineage, explicitly instructed to try to falsify rather than confirm. A single prompt has no mechanism to do this at all. Even a multi-step chain gains little if every step runs on the same underlying model.

---

## 3. Domain whitelisting instead of open web search

**Naive approach.** Let the retrieval step search the open web for evidence — more sources, better coverage, fewer `NO_EVIDENCE` results.

**Why it fails.** Open web search reintroduces exactly the problem VERITAS exists to solve: any sufficiently confident-sounding page can become "evidence," including content that is itself unverified, outdated, or written by another LLM. A grounding step that grounds against ungrounded content isn't grounding — it's laundering.

**What VERITAS does instead.** Retrieval ([`veritas/whitelist.py`](../veritas/whitelist.py), [`veritas/nodes/n4_retrieve.py`](node_reference.md#n4--evidence-retrieval)) is restricted to a small, fixed list of authoritative domains per subject area — WHO, DDA, MOHP, NCBI, CDC, NICE for health; the Nepal Law Commission, Ministry of Law, and Supreme Court for legal; FAO, MOALD, NARC for agriculture. If a claim has zero evidence within that whitelist, it is marked `NO_EVIDENCE` and reported honestly rather than silently widened to a general search. The direct cost of this decision is visible in the benchmark: some domains (agriculture, some legal questions) have real, measurable gaps in whitelisted source availability. That's reported as a finding about source availability by domain, not smoothed over.

---

## 4. Atomic claim decomposition

**Naive approach.** Answer the question as posed, as one unit.

**Why it fails.** Real high-stakes questions are rarely atomic. "My 2-year-old has fever and I have paracetamol, how much do I give?" bundles at minimum: the correct drug class for paediatric fever, whether dosing is weight- or age-based, the actual mg/kg figure, and red-flag conditions that override home treatment entirely. A single-prompt system answers the gestalt and will confidently get the one sub-fact it's weakest on wrong, buried inside an otherwise-plausible paragraph — the reader has no way to tell which part of the answer to distrust.

**What VERITAS does instead.** N3 splits the question into 2–6 independently verifiable claims, each carrying its own criticality flag (numeric claims — doses, deadlines, thresholds, rates — are always forced `critical`). Each claim gets its own evidence, its own verdict, and its own adversarial challenge. A system with partial knowledge should produce a partial, clearly-labelled answer — not a complete, confidently wrong one.

---

## 5. Back-translation fidelity checking

**Naive approach.** Trust that a response verified correct in English stays correct once translated into Nepali.

**Why it fails.** Translation is where safety guarantees quietly die. A pipeline can verify every single claim with genuine rigor in English, and then the final generation step can drop a negation, soften a refusal into a hedge, or shift a number — and by construction, that failure is invisible to anyone reading only the Nepali output, because it looks exactly like a normal, fluent answer. Almost no comparable system checks for this, precisely because it requires a second, independent pass *after* the content is already believed finished.

**What VERITAS does instead.** N9 translates the final response literally back into English and diffs it against the verified claim set, flagging any high-severity drift — an added claim, a dropped caveat, a number that changed, or a refusal that became an answer. On drift, the orchestrator retries synthesis once with the drift report attached; if that still fails, it degrades to a bilingual side-by-side response (the translation plus the verified English claim summary) instead of silently shipping a version that might have quietly become unsafe.

---

## What ties these together

Every one of these five decisions follows the same shape: identify the specific point where a single LLM call would have to be simultaneously creative and reliable, and split those two requirements into different components — an LLM for the creative/generative part, and either a different model or deterministic code for the part that needs to be reliable. That's the actual definition of "workflow, not chain" used throughout this project: not more steps for their own sake, but steps that exist because a single step structurally cannot do both jobs at once.
