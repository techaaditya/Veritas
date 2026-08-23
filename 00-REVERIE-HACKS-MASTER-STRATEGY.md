# Reverie Hacks 2026 — Master Strategy

**Prepared for:** Aaditya (KU, Dept. of AI)
**Prepared:** 22 Aug 2026
**Event:** https://reverie-hacks-2026.devpost.com/

---

## 1. The two facts that determine everything

### 1.1 You have ~40 hours, not weeks

| | |
|---|---|
| Devpost deadline | **Aug 24, 2026 @ 12:00 AM CDT** |
| In UTC | Aug 24, 05:00 UTC |
| **In Nepal time (UTC+5:45)** | **Sunday 24 Aug, 10:45 AM NPT** |
| Time from now (Sat 22 Aug) | **~40 hours including sleep** |

**Hard rule: treat Saturday 23 Aug, 9:00 PM NPT as your real deadline.** Devpost submission forms break, videos fail to upload, and there is no late window ("Late submissions will not be considered"). A 13-hour buffer is not paranoia, it's the difference between two submissions and zero.

### 1.2 The prize pool is 95% inflated

Here's the actual breakdown of what is real cash vs. what is sponsor credit given to *everyone*:

**Real cash (this is the entire cash pool):**

| Prize | Amount | Winners |
|---|---|---|
| 1st Place — **ML Prompt Engineering** or **Ideathon** | **$100** | 2 |
| 1st Place — any other track | $90 | 4 |
| 2nd Place — any track | $40 | 6 |
| **Total actual cash across all 1,913 participants** | **$980** | |

**Everything else is non-cash.** The listing even states it: *"THIS IS NOT A CASH PRIZE... cannot be exchanged or redeemed for cash."* The $2.2M figure is computed by multiplying free trial subscriptions by 1,950 participants. Every participant gets ~$1,100 of "prizes" just for registering.

**So: do not do this hackathon for the money.** Realistic max cash if you win two tracks: **$190**.

### 1.3 Where the *actual* value is

Ranked by what genuinely helps you:

1. **Learner Labs internship — 6 slots, ML Prompt Engineering + Ideathon winners ONLY.** This is the single most valuable thing on the board. Real AI-startup experience + a strong LoR. For a Year IV AI student targeting data science, this is worth more than every other prize combined. **It is only reachable through two tracks.**
2. **Momen $2,000 credits** — Software Development 1st place only.
3. **CodeCrafters 2-year VIP ($720)** — Software Development 1st only.
4. **Neon $500 credits** (5 winners), **Render $500** (SWE 1st, *must use Render in the project*).
5. **Featherless.AI $300 API credit** — "winner of the AI/ML track."
6. **Formaloo CEO mentoring session** — Datathon 1st only.
7. **Devpost win on your public portfolio + 3 free domains** — small but real, and it compounds for GitHub Campus Expert / grad applications.
8. **Free participant perks you should claim regardless:** Featherless 1 month, Firecrawl 10k credits, Wolfram|One 1 month, Render 1 month, Mobbin 3 months, Momen $100, Somba 3 months, Dialogate Pro **lifetime**, 500 Protoflow credits, 500 PerfectCorp API credits (first 700 only — claim today).

---

## 2. Track selection — my recommendation

### The recommendation: **ML Prompt Engineering (primary) + Ideathon (secondary)**

**Why these two:**

| Factor | ML Prompt Eng | Ideathon | Software Dev | Datathon | App Dev | Embedded |
|---|---|---|---|---|---|---|
| Cash for 1st | **$100** | **$100** | $90 | $90 | $90 | $90 |
| Internship eligible | **YES** | **YES** | No | No | No | No |
| Code required | Minimal | **None** | Full app | Notebook | Full app | Firmware+PCB |
| Buildable in 20h | **Yes** | **Yes** | Risky | Yes | Risky | No (no hardware) |
| Expected competition | **Low** | Medium | **Highest** | Medium | High | Lowest |
| Plays to your skills | High | High | High | High | Medium | Low |

The decisive logic:

- **The internship is only in these two tracks.** Every other track caps out at credits you'll mostly not use.
- **These are the two tracks most people skip.** Out of 1,913 participants, the overwhelming majority will submit to Software Development and App Development because that's what "hackathon" means to them. ML Prompt Engineering has a weird, unfamiliar deliverable set (flowchart PNG + comparison samples + docs) that scares people off. Fewer competitors, same prize, higher prize.
- **Neither requires a shipped application.** In 40 hours, a half-finished web app is a guaranteed loss. A rigorous workflow + a rigorous business plan are both fully completable.
- **They're both writing-and-thinking heavy**, which is where you're strong and where a Year IV AI student can visibly out-execute 15-year-olds.

**Critically: do NOT submit the same project to both tracks.** Judges cross-check, and a recycled submission looks lazy. The two projects below are deliberately in different domains.

### If you want a technical flex instead of Ideathon

Swap Ideathon → **Datathon**. It's the third-best track: notebook + report + demo video is completable in ~14 hours, competition is moderate, the Formaloo CEO mentoring is a real networking asset, and it directly signals "data scientist" on your portfolio. You lose internship eligibility on that half. See §3.4 for three Datathon ideas.

### What to avoid

- **Embedded Systems:** the track only needs schematics + firmware + a demo video, but "demo video of the designed product" effectively requires hardware you can't source and assemble by Sunday morning. Skip.
- **Software Development:** highest competition, richest sponsor prizes, but you'd need a polished, deployed, documented app *plus* Render deployment to qualify for the Render prizes. Not in 20 hours alongside a second project. This is the track to target at the next hackathon with a two-week runway.

---

## 3. Idea bank — 3 ranked ideas per track

Ranking within each track is by **expected win probability given your constraints**, not by coolness.

### 3.1 ML PROMPT ENGINEERING

*Judged on: does your multi-node workflow demonstrably beat a single prompt? The comparison sample is the whole ballgame. Pick a task where single prompts fail visibly and measurably.*

**#1 — VERITAS: Refusal-Aware Grounded Answering for Low-Resource Languages** ⭐ **BUILD THIS**
A pipeline that answers high-stakes health/legal questions in Nepali by decomposing the query into atomic claims, grounding each one against whitelisted authoritative sources via Firecrawl, cross-verifying with a *second* model that is instructed to falsify, and then **refusing rather than guessing** when evidence is insufficient. Single-prompt GPT/Gemini confidently fabricates Nepali drug dosages and invents law article numbers — that failure is dramatic, reproducible, and instantly legible to a judge. Full build doc: `01-PROJECT-A-VERITAS.md`.

**#2 — AUTOPSY: A Prompt-Engineering Workflow That Does Prompt Engineering**
You feed it a prompt that's failing plus example bad outputs. It runs a diagnostic tree — classifies the failure mode (ambiguity, missing context, format drift, refusal-overtriggering, reasoning collapse), generates three targeted repairs, A/B tests them against a held-out case set, and outputs a repaired prompt with a diff and an evidence table. Highest innovation ceiling in the entire hackathon: it's a self-referential submission to a prompt-engineering track, which judges will remember out of 1,900 entries. Riskier because "does it beat a single prompt?" is more abstract to demo. Build this if VERITAS feels too safe.

**#3 — SOCRATES: Misconception-Modeling Tutor**
Instead of generating practice questions, it first infers *why* a student got something wrong (a model of their specific misconception), then generates a question designed to make that misconception produce a visibly wrong answer, then adapts. Single prompts generate generic questions; this generates diagnostic ones. Strong, but the win depends on educational judging taste, which is less predictable than "we eliminated hallucinations."

### 3.2 IDEATHON

*Judged on: real problem, real customer who pays, coherent business model canvas. Tech is almost irrelevant. The submission is a ≤5-min pitch video + a PDF plan.*

**#1 — PRAMAAN: A Verified Skills Passport for Migrant Workers** ⭐ **BUILD THIS**
~2,000 Nepalis leave daily for foreign employment. Their real skills — welding, scaffolding, tiling, caregiving, heavy equipment — are invisible and unverifiable, so recruiters discount everyone to "unskilled" wages. PRAMAAN is a portable, verifiable skills credential built from practical assessment + employer attestation + timestamped work evidence, sold to the *employers* who bear the cost of bad hires. Enormous underserved market, clear payer, defensible network effect, and a problem no judge on that panel will have seen before. Full build doc: `02-PROJECT-B-PRAMAAN.md`.

**#2 — SHEETAL: Cold-Chain-as-a-Service by the Crate**
Nepali smallholders lose 25–35% of horticulture output post-harvest with zero access to cold storage. Instead of selling farmers a cold room they can't afford, deploy solar-powered modular cold units at collection centres and charge **per crate per day** — a variable cost that matches a farmer's variable income. Revenue: crate-days, plus a spread on aggregated cold-chain-enabled sales to urban buyers. Very credible unit economics, physically real, ESG-friendly. Slightly less novel than PRAMAAN — cold chain startups exist in India — so your differentiation must be the *pricing model*, not the cold room.

**#3 — SETU: Verified Medical Escrow for Diaspora Families**
A migrant worker in Qatar gets a call: "your mother needs surgery, send NPR 300,000." They cannot verify the diagnosis, the hospital, or the price, and there is a real fraud industry around exactly this. SETU lets the worker pay a **verified hospital directly**, against an itemised, hospital-confirmed estimate, with photo/report verification and staged disbursement. Revenue: FX spread + hospital partnership fees + a small verification fee. Emotionally powerful pitch, real fraud problem, clear money flow. Ranked third only because it's regulatorily heavy (money transmission licensing) and judges may probe that.

### 3.3 SOFTWARE DEVELOPMENT

*If you change your mind: deploy on **Render** — it's a hard requirement for the $500/$300/$100 Render prizes, and Momen $2,000 + CodeCrafters $720 also sit here.*

**#1 — REGRESSION RADAR: CI for LLM-Powered Apps**
Everyone is shipping LLM features; nobody has tests for them. A GitHub Action that runs your prompts against a versioned eval set on every PR and fails the build on *semantic* regression — not string diffs, but rubric-scored behaviour drift, cost drift, and latency drift, with a rendered report comment on the PR. Timely, technically credible, and every judge on that panel has personally felt this pain. Highest win probability in this track.

**#2 — REPO2RUNBOOK: Executable Onboarding for Any Codebase**
Point it at a GitHub repo. It infers the architecture, generates a dependency-resolved dev environment, and produces a *guided, runnable* tour — "run this, now break this line, see what fails, now fix it." Solves the real onboarding problem (docs go stale, environments don't reproduce). Uses Firecrawl for docs ingestion, Render for the hosted playground.

**#3 — DRIFTLESS: Offline-First Sync Engine for Low-Connectivity Regions**
A CRDT-based sync layer + SDK for apps that must work through multi-day outages, with conflict-resolution policies expressed declaratively. Less flashy, more genuinely hard, and grounded in your Nepal context. Judges reward feasibility and depth here, but it's the least demo-able of the three.

### 3.4 DATATHON

*Notebook + dataset link in README + written report + demo video. The differentiator is going beyond "we found a correlation" into an actual decision recommendation.*

**#1 — Attributable Health Burden of Kathmandu Valley Air Pollution**
Combine OpenAQ / CAMS PM2.5 series with meteorological reanalysis and health-facility admission proxies. Don't just plot pollution — build a source-apportionment-informed model and translate it into **attributable admissions per µg/m³**, then simulate three concrete policy interventions (brick kiln seasonality, vehicle restriction days, valley inversion-triggered alerts). Local, high impact, and the "insight → decision" jump is exactly what the track description asks for.

**#2 — Rainfall-Triggered Landslide Susceptibility for Nepal's Mid-Hills**
Open geospatial layers (slope, lithology, land cover, road cuts) + rainfall reanalysis + a landslide inventory. Train a susceptibility model, then evaluate it as an *early-warning system* — precision/recall at operational alert thresholds, not just AUC. The evaluation framing alone will beat 90% of entries.

**#3 — Remittance Dependence and Human Capital**
Use Nepal Living Standards / World Bank / open household survey data to examine how household remittance income relates to school enrolment, dropout timing, and gender gaps in education. Unusual for a datathon (econometric rather than predictive), which makes it stand out, and the "identify patterns *and analyse them for a solution*" requirement is naturally satisfied. Weakest on the "trained model" deliverable — mitigate by including a predictive dropout-risk model alongside the analysis.

### 3.5 APP DEVELOPMENT

**#1 — BAZAAR BHAU: Crowdsourced Farm-Gate Price Truth**
Farmers get told whatever price the middleman feels like. An offline-first mobile app where farmers submit today's gate price with photo + GPS + timestamp, cross-validated against the Kalimati wholesale feed, surfacing a confidence-weighted local price band. On-device outlier detection so it works without connectivity. Simple, deeply useful, demos beautifully.

**#2 — SAAS: Sign-Language-First Accessibility Layer**
On-device fingerspelling and common-sign recognition (TFLite) that turns Nepali Sign Language into text within any app via an accessibility keyboard. Very strong on the "Accessibility" judging criterion, which almost nobody optimises for.

**#3 — LOOP: Post-Disaster Family Reunification Over Mesh**
BLE/Wi-Fi Direct mesh app for the 72 hours after an earthquake when towers are down — status broadcasts, store-and-forward relay, and a QR-based identity claim. Nepal-relevant, technically distinctive. Hardest to demo convincingly without multiple devices.

### 3.6 EMBEDDED SYSTEMS

*Not recommended in this window — the demo video requirement effectively needs physical hardware. Listed for completeness / a future event.*

**#1 — Seismic Gas Cutoff Valve.** An accelerometer-triggered LPG shutoff plus continuous MQ-series leak sensing. Post-2015-earthquake Nepal, secondary fires after quakes are a documented killer. Clear, life-safety, cheap BOM.

**#2 — Solar Irrigation Pump Controller.** MPPT-aware scheduling that runs the pump when insolation and soil-moisture deficit jointly justify it, with a dry-run cutoff to protect the pump. Real, saleable, agriculturally grounded.

**#3 — Community Tap Water-Quality Logger.** Turbidity + TDS + temperature with LoRa uplink to a ward-level dashboard, solar + supercap powered. Strong sustainability score.

---

## 4. The 40-hour execution plan

All times **Nepal Standard Time**. Adjust the start block to whenever you actually read this.

### Saturday 22 Aug

| Time | Block | Output |
|---|---|---|
| **Now → +30 min** | **Register on Devpost.** Join the hackathon, join their Discord, claim the PerfectCorp 500 API credits (first 700 only, first-come). Create both draft submissions immediately — an empty draft you edit later is far safer than creating one at 3 AM. | 2 draft submissions exist |
| +30m → 1h | Read `01-PROJECT-A-VERITAS.md` end to end. Get a Gemini API key and an OpenAI or Featherless key. Get the Firecrawl key from the participant perk. | Keys working |
| 1h → 5h | **VERITAS: build the pipeline.** Nodes 1–6. Get one question flowing end to end before you polish anything. | Working pipeline |
| 5h → 6h | Break. Eat. Actually eat. | — |
| 6h → 9h | **VERITAS: build the 30-question benchmark and run both arms** (single-prompt baseline vs. full pipeline). Save every raw output. This is your winning artifact. | `results.csv` + raw logs |
| 9h → 11h | **VERITAS: flowchart PNG + documentation.md.** | 2 of 3 deliverables |
| 11h → 12h | Sleep. Non-negotiable — a tired judgement call at hour 30 costs more than the hour. | — |

### Sunday 23 Aug

| Time | Block | Output |
|---|---|---|
| Morning, 4h | **PRAMAAN: write the full project plan PDF.** Read `02-PROJECT-B-PRAMAAN.md`; the structure is already laid out, you're filling and sharpening. | Plan PDF |
| Midday, 2h | **PRAMAAN: build 5–6 mockup screens** (Figma, or Momen with your free $100 credit — using a sponsor tool is a small but free scoring nudge). Export into the PDF. | Mockups in PDF |
| +1h | **PRAMAAN: record the ≤5-min pitch video.** Script is in the doc. Three takes max, then ship. | Pitch video |
| +2h | **VERITAS: record the comparison demo video.** Side-by-side, single prompt vs. pipeline, on 3 chosen cases. | Comparison video |
| **By 9:00 PM** | **SUBMIT BOTH.** Upload files, paste links, hit submit, screenshot the confirmation. | Done |
| 9 PM → deadline | Buffer for everything that will go wrong. If nothing goes wrong, polish the READMEs. | — |

### If you fall behind — cut in this order

1. Cut the VERITAS demo video down to a 90-second screen recording with captions.
2. Cut the benchmark from 30 questions to 15 (keep all three tiers represented).
3. Cut PRAMAAN mockups from 6 screens to 3.
4. **Never cut:** the flowchart PNG, the single-prompt-vs-pipeline comparison, the pitch video. Those three are literally the graded deliverables.

---

## 5. Reverse-engineering the judging rubric

Five criteria. Here's what each one actually rewards and how each project hits it.

| Criterion | What judges are really asking | VERITAS hits it by | PRAMAAN hits it by |
|---|---|---|---|
| **Innovation** | "Have I seen this before today?" | Refusal-as-a-feature + cross-model adversarial falsification + low-resource-language grounding — an unusual combination | Selling verification to the party that bears hiring risk, not to the worker or the agency |
| **Problem Solving** | Real problem? Does it work? Feasible? | Measured hallucination rate drop on a real benchmark, not a vibe | 2,000 departures/day, documented wage discounting, named payer |
| **Sustainability / Scalability** | Does this survive contact with reality? | Model-agnostic node design; costs scale linearly and are computed | Unit economics table with a per-verification margin; corridor-by-corridor expansion path |
| **UX & Design** | Is it intuitive, polished, accessible? | Citation cards + explicit "what we could NOT verify" section + Nepali-first output | Low-literacy-first UI, offline QR verification, voice guidance |
| **Bonus: Exceptionality** | "This one is different." | The benchmark. Almost nobody in a student hackathon builds a real eval harness. | The honest risk section — naming who loses if you win |

**The two highest-leverage moves, in order:**

1. **Measure something.** In a field of 1,900 student submissions, the entry that says "hallucination rate dropped from 47% to 3% across 30 held-out questions, here's the CSV" wins against a hundred entries that say "our AI is very powerful." This single decision is worth more than any feature.
2. **Name your own weaknesses first.** Every judge on that panel is a working engineer or PM. They will find the hole. If you find it first and address it, you convert their scepticism into trust. Judges have seen a thousand overclaiming pitches; almost none that self-critique.

---

## 6. Submission checklists

### ML Prompt Engineering — 3 required uploads

- [ ] **ML workflow PNG** — flowchart showing: where human input enters, every LLM query, *which model* each node uses, what each node does. Label every node. Export at ≥2000px wide.
- [ ] **Samples** — video or document showing your workflow on test cases **compared against a single-prompt approach on the same cases**. The comparison is mandatory, not optional. This is where most entrants will be weak.
- [ ] **Documentation** — reasoning behind *each node*, how it works, supporting data.
- [ ] Devpost fields: inspiration, what it does, how we built it, challenges, accomplishments, what we learned, what's next, built-with tags.

### Ideathon — 2 required uploads

- [ ] **Pitch presentation video, ≤5:00** — purpose + key details. Going over 5:00 risks disqualification; target 4:30.
- [ ] **Project plan PDF** — purpose, technical details, **mockups**, logistics, future plans, and the full canvas: Value Proposition, Customer Segments, Channels, Customer Relationships, Revenue Streams, Key Resources, Key Activities, Cost Structure.
- [ ] Put the *depth* in the PDF and only the *hooks* in the video — the organisers explicitly say to do this.

### Universal

- [ ] Both projects list you (and up to 2 teammates) correctly — teams are 1–3.
- [ ] Any repos are **public** with a **LICENSE file** (MIT is fine and is what they recommend).
- [ ] Videos are **unlisted YouTube**, not private. A private video is a zero.
- [ ] Third-party assets attributed.
- [ ] Screenshot each submission confirmation.

---

## 7. Resources

**APIs / models**
- Gemini API — https://aistudio.google.com (generous free tier; use `gemini-2.0-flash` class for cheap nodes)
- Featherless.AI — your participant perk; gives you Llama/GPT/Claude-class access for the cross-model verifier node
- Firecrawl — 10k free credits from the participant perk; use it for grounded retrieval and *say so* (sponsor usage is a free nudge)

**Design / docs**
- Excalidraw or draw.io — flowchart PNG
- Mermaid — versionable diagrams inside your README
- Figma — mockups; Mobbin (participant perk) for UI pattern reference
- Momen — $100 participant credit; fastest path to clickable mockups

**Recording**
- OBS Studio (free) or CleanShot X — screen recording
- Keep pitch video: 1080p, clear audio, face-cam optional. Audio quality matters more than video quality. Record in a small room with soft furnishings.

**Data (if you pivot to Datathon)**
- Kaggle, OpenAQ, World Bank Open Data, Nepal Open Data Portal, HDX (Humanitarian Data Exchange — excellent Nepal coverage)

**Sanity checks**
- Devpost's own submission help: https://help.devpost.com/
- Reverie Discord — linked from the Devpost page; ask ambiguity questions there early, not at hour 38

---

## 8. Honest expected value

Let me not sell you a fantasy.

- **Probability of winning 1st in at least one track:** meaningfully better than random given the quality gap you can create with a real benchmark and a real business model — but there are ~1,900 participants and some will be very good. Call it a genuine shot, not a lock.
- **Realistic cash outcome:** $0–$190.
- **The real return:** two portfolio-grade artifacts, a Devpost win badge if it lands, credible material for GitHub Campus Expert and grad applications, a shot at the Learner Labs internship, and — if you build VERITAS properly — an eval harness and a grounded-generation pipeline that plug directly into your ILPRL guardrails internship work. That last one is the highest-value output regardless of whether you place.

Build for that, and the placement is a bonus rather than the point.
