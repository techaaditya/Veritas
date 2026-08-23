/* VERITAS — "The Tribunal" frontend. Vanilla JS, no build step. */

const NODES = [
  { id: "N1", label: "Language & Intent Normalizer", model: "gemini-3.6-flash", executor: "gemini", desc: "Detects language, normalizes to Devanagari + canonical English, flags ambiguities." },
  { id: "N2", label: "Risk Tier Gate", model: "gemini-3.6-flash", executor: "gemini", desc: "Classifies TIER_0 / TIER_1 / TIER_2. TIER_0 halts the pipeline." },
  { id: "N3", label: "Claim Decomposer", model: "gpt-oss:120b", executor: "ollama", desc: "Splits the question into 2–6 atomic, independently verifiable claims." },
  { id: "N4", label: "Evidence Retrieval", model: "Firecrawl · whitelist", executor: "tool", desc: "Site-restricted search over authoritative domains, per claim." },
  { id: "N5", label: "Grounded Answerer", model: "gemini-3.6-flash", executor: "gemini", desc: "Answers each claim from evidence only. No evidence, no answer." },
  { id: "N6", label: "Adversarial Verifier", model: "gpt-oss:120b", executor: "ollama", desc: "A different model family tries to falsify each answer." },
  { id: "N7", label: "Refusal Arbiter", model: "deterministic Python", executor: "python", desc: "Rules-based decision: ANSWER / PARTIAL_ANSWER / REFUSE. No LLM." },
  { id: "N8", label: "Synthesizer", model: "gemini-3.6-flash", executor: "gemini", desc: "Composes the final response in the user's language, from verified claims only." },
  { id: "N9", label: "Back-Translation Fidelity Check", model: "gemini-3.6-flash", executor: "gemini", desc: "Translates the answer back to English to catch drift. One retry on failure." },
];

const EXAMPLES = [
  { label: "Dosing question", tier: "amber", q: "मेरो २ वर्षको बच्चालाई ज्वरो छ, प्यारासिटामोल कति दिने?" },
  { label: "Unanswerable claim", tier: "vermilion", q: "Is it safe to take ivermectin for dengue fever in Nepal?" },
  { label: "TIER-0 emergency", tier: "vermilion", q: "मेरो श्रीमानको छातिमा दुखेको छ र सास फेर्न गाह्रो भइरहेको छ" },
];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const els = {
  form: $("#query-form"),
  input: $("#question-input"),
  runBtn: $("#run-button"),
  chips: $("#example-chips"),
  baselineBody: $("#baseline-body"),
  nodeSpine: $("#node-spine"),
  claimsPanel: $("#claims-panel"),
  claimsGrid: $("#claims-grid"),
  graveyard: $("#graveyard"),
  graveyardGrid: $("#graveyard-grid"),
  arbiterStamp: $("#arbiter-stamp"),
  finalAnswer: $("#final-answer"),
  tier0Overlay: $("#tier0-overlay"),
  scorecardToggle: $("#scorecard-toggle"),
  scorecardPanel: $("#scorecard-panel"),
  scorecardContent: $("#scorecard-content"),
  arena: $("#arena"),
  queryBar: document.querySelector(".query-bar"),
};

let claimCardEls = {}; // claim_id -> element
let claimState = {};   // claim_id -> {question, criticality, verdict, ...}
let nodeSourcesSeen = { N4: new Set(), N5: new Set(), N6: new Set() };

function renderChips() {
  els.chips.innerHTML = "";
  for (const ex of EXAMPLES) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.innerHTML = `<span class="chip-tier" style="background:var(--${ex.tier})"></span>${ex.label}`;
    btn.addEventListener("click", () => {
      els.input.value = ex.q;
      els.input.focus();
    });
    els.chips.appendChild(btn);
  }
}

function renderNodeSpine() {
  els.nodeSpine.innerHTML = "";
  for (const n of NODES) {
    const li = document.createElement("li");
    li.className = "node-row";
    li.dataset.node = n.id;
    li.dataset.executor = n.executor;
    li.title = n.desc;
    li.innerHTML = `
      <span class="node-dot"></span>
      <span class="node-label">${n.id} · ${n.label}</span>
      <span class="node-model">${n.model}</span>
      <span class="node-status">pending</span>
      <div class="node-detail"></div>
    `;
    li.addEventListener("click", () => li.classList.toggle("expanded"));
    els.nodeSpine.appendChild(li);
  }
}

function nodeRow(id) {
  return els.nodeSpine.querySelector(`.node-row[data-node="${id}"]`);
}

function setNodeState(id, state, statusText, detail) {
  const row = nodeRow(id);
  if (!row) return;
  row.classList.remove("active", "done", "halted");
  if (state) row.classList.add(state);
  const statusEl = row.querySelector(".node-status");
  if (statusText) statusEl.textContent = statusText;
  if (detail !== undefined) {
    row.querySelector(".node-detail").textContent =
      typeof detail === "string" ? detail : JSON.stringify(detail, null, 2);
  }
}

function resetUI() {
  els.baselineBody.innerHTML = '<p class="placeholder">Streaming…</p><span class="cursor"></span>';
  renderNodeSpine();
  els.claimsPanel.hidden = true;
  els.claimsGrid.innerHTML = "";
  els.graveyard.hidden = true;
  els.graveyardGrid.innerHTML = "";
  els.arbiterStamp.hidden = true;
  els.arbiterStamp.className = "arbiter-stamp";
  els.arbiterStamp.innerHTML = "";
  els.finalAnswer.hidden = true;
  els.finalAnswer.innerHTML = "";
  els.tier0Overlay.hidden = true;
  els.tier0Overlay.innerHTML = "";
  claimCardEls = {};
  claimState = {};
  nodeSourcesSeen = { N4: new Set(), N5: new Set(), N6: new Set() };
}

function claimCardHTML(c) {
  return `
    <div class="claim-id"><span>${c.id}</span><span class="badge ${c.criticality}">${c.criticality}</span></div>
    <div class="claim-q">${escapeHTML(c.claim_question)}</div>
    <div class="claim-badges">
      <span class="badge status-verdict">pending</span>
    </div>
    <div class="claim-source"></div>
  `;
}

function escapeHTML(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function ensureClaimCard(c) {
  if (claimCardEls[c.id]) return claimCardEls[c.id];
  const div = document.createElement("div");
  div.className = "claim-card";
  div.innerHTML = claimCardHTML(c);
  els.claimsGrid.appendChild(div);
  claimCardEls[c.id] = div;
  claimState[c.id] = { ...c, verdict: null, challenge: null };
  return div;
}

function updateClaimCard(claimId, patch) {
  const card = claimCardEls[claimId];
  if (!card) return;
  Object.assign(claimState[claimId], patch);
  const st = claimState[claimId];

  const badgesEl = card.querySelector(".claim-badges");
  const badges = [];
  if (st.status === "NO_EVIDENCE") badges.push(`<span class="badge UNSUPPORTED">NO_EVIDENCE</span>`);
  if (st.verdict) badges.push(`<span class="badge ${st.verdict}">${st.verdict}</span>`);
  if (st.challenge?.verdict_after_challenge) {
    badges.push(`<span class="badge ${st.challenge.verdict_after_challenge}">${st.challenge.verdict_after_challenge}</span>`);
  }
  if (badges.length === 0) badges.push(`<span class="badge status-verdict">pending</span>`);
  badgesEl.innerHTML = badges.join("");

  const sourceEl = card.querySelector(".claim-source");
  if (st.sources?.length) sourceEl.textContent = st.sources.join(" · ");

  const isDead =
    st.verdict === "UNSUPPORTED" ||
    st.verdict === "CONTRADICTED" ||
    st.challenge?.verdict_after_challenge === "FAILS";

  if (isDead && !card.classList.contains("dead")) {
    card.classList.add("dead");
    els.graveyard.hidden = false;
    els.graveyardGrid.appendChild(card);
  }
}

function showArbiter(decision, reasons) {
  const el = els.arbiterStamp;
  el.hidden = false;
  el.className = `arbiter-stamp ${decision}`;
  const reasonList = (reasons || []).map((r) => `<li>${escapeHTML(r)}</li>`).join("");
  el.innerHTML = `
    <div class="decision">${decision.replace("_", " ")}</div>
    ${reasonList ? `<ul class="arbiter-reasons">${reasonList}</ul>` : ""}
  `;
}

function showFinal(data) {
  const el = els.finalAnswer;
  el.hidden = false;
  const citations = (data.citations || [])
    .map((c) => `<div>${escapeHTML(c.marker)} <a href="${c.url}" target="_blank" rel="noopener">${escapeHTML(c.url)}</a></div>`)
    .join("");
  const degraded = (data.degraded_nodes || []).length
    ? `<div class="degraded-note">⚠ degraded nodes (fell back): ${data.degraded_nodes.join(", ")}</div>`
    : "";
  el.innerHTML = `
    <div class="devanagari">${escapeHTML(data.response_text || "")}</div>
    ${citations}
    ${degraded}
    <div class="final-meta">
      <span>tier: ${data.tier ?? "—"}</span>
      <span>decision: ${data.decision ?? "—"}</span>
      <span>cost: $${(data.total_cost_usd ?? 0).toFixed(6)}</span>
      <span>latency: ${(data.total_latency_ms ?? 0).toFixed(0)} ms</span>
    </div>
  `;
}

function showTier0(data) {
  const card = data.card || {};
  const contacts = (card.contacts || []).map((c) => `<li>${escapeHTML(c)}</li>`).join("");
  const signals = (data.emergency_signals || []).join(", ");
  els.tier0Overlay.hidden = false;
  els.tier0Overlay.innerHTML = `
    <div class="tier0-card">
      <h2>${escapeHTML(card.heading || "Emergency detected")}</h2>
      <p>${escapeHTML(card.body || "")}</p>
      ${signals ? `<div class="tier0-signals">detected: ${escapeHTML(signals)}</div>` : ""}
      <ul class="tier0-contacts">${contacts}</ul>
      <button class="tier0-dismiss" type="button">I understand — show the trace</button>
    </div>
  `;
  els.tier0Overlay.querySelector(".tier0-dismiss").addEventListener("click", () => {
    els.tier0Overlay.hidden = true;
  });
}

/* ---------------------------------------------------------------------- */
/* Streaming                                                              */
/* ---------------------------------------------------------------------- */

function streamSSE(url, onEvent) {
  const es = new EventSource(url);
  const types = ["node_start", "node_done", "claim_update", "arbiter", "halt", "final", "error", "chunk", "done"];
  for (const t of types) {
    es.addEventListener(t, (e) => {
      let data = {};
      try { data = JSON.parse(e.data); } catch { /* ignore */ }
      onEvent(t, data);
      if (t === "final" || t === "done" || t === "error") es.close();
    });
  }
  es.onerror = () => {
    onEvent("error", { reason: "connection lost" });
    es.close();
  };
  return es;
}

function runBaseline(question) {
  els.baselineBody.innerHTML = "";
  const textEl = document.createElement("span");
  const cursor = document.createElement("span");
  cursor.className = "cursor";
  els.baselineBody.appendChild(textEl);
  els.baselineBody.appendChild(cursor);

  streamSSE(`/api/baseline?q=${encodeURIComponent(question)}`, (type, data) => {
    if (type === "chunk") {
      textEl.textContent += data.text;
    } else if (type === "done") {
      cursor.remove();
    } else if (type === "error") {
      cursor.remove();
      const err = document.createElement("div");
      err.className = "degraded-note";
      err.textContent = `⚠ ${data.reason}`;
      els.baselineBody.appendChild(err);
    }
  });
}

function runVeritas(question) {
  streamSSE(`/api/veritas?q=${encodeURIComponent(question)}`, (type, data) => {
    switch (type) {
      case "node_start":
        setNodeState(data.node, "active", "running…");
        break;

      case "node_done":
        setNodeState(data.node, "done", "done", data);
        if (data.node === "N3" && Array.isArray(data.claims)) {
          els.claimsPanel.hidden = false;
          for (const c of data.claims) ensureClaimCard(c);
        }
        break;

      case "claim_update": {
        const node = data.node; // N4 | N5 | N6
        if (node === "N4") {
          setNodeState("N4", "active", "running…");
          updateClaimCard(data.claim_id, { status: data.status, sources: data.sources });
        } else if (node === "N5") {
          setNodeState("N5", "active", "running…");
          updateClaimCard(data.claim_id, { verdict: data.verdict });
        } else if (node === "N6") {
          setNodeState("N6", "active", "running…");
          updateClaimCard(data.claim_id, {
            challenge: { verdict_after_challenge: data.verdict_after_challenge, flags: data.flags },
          });
        }
        break;
      }

      case "arbiter":
        setNodeState("N4", "done", "done");
        setNodeState("N5", "done", "done");
        setNodeState("N6", "done", "done");
        setNodeState("N7", "done", data.decision, data);
        showArbiter(data.decision, data.reasons);
        break;

      case "halt":
        setNodeState("N2", "halted", "TIER_0 — halted", data);
        showTier0(data);
        break;

      case "final":
        showFinal(data);
        els.runBtn.disabled = false;
        break;

      case "error":
        els.runBtn.disabled = false;
        if (data.reason) {
          const err = document.createElement("div");
          err.className = "degraded-note";
          err.textContent = `⚠ pipeline error: ${data.reason}`;
          els.finalAnswer.hidden = false;
          els.finalAnswer.appendChild(err);
        }
        break;
    }
  });
}

/* ---------------------------------------------------------------------- */
/* Wiring                                                                 */
/* ---------------------------------------------------------------------- */

els.form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = els.input.value.trim();
  if (!q) return;
  els.runBtn.disabled = true;
  resetUI();
  runBaseline(q);
  runVeritas(q);
});

els.scorecardToggle.addEventListener("click", async () => {
  const showing = els.scorecardPanel.hidden;
  els.scorecardPanel.hidden = !showing;
  els.arena.hidden = showing;
  els.queryBar.hidden = showing;
  els.scorecardToggle.setAttribute("aria-pressed", String(showing));
  if (showing) await loadScorecard();
});

async function loadScorecard() {
  try {
    const res = await fetch("/api/benchmark");
    const data = await res.json();
    if (!data.available) return; // placeholder already in the DOM
    renderScorecard(data);
  } catch {
    /* leave placeholder */
  }
}

function renderScorecard(data) {
  const metrics = data.metrics || [];
  const rows = metrics
    .map(
      (m) => `
      <tr>
        <td>${escapeHTML(m.name)}</td>
        <td class="${m.veritas_wins ? "win" : ""}">${escapeHTML(String(m.veritas))}</td>
        <td class="${!m.veritas_wins ? "lose" : ""}">${escapeHTML(String(m.baseline))}</td>
      </tr>`
    )
    .join("");
  const losses = (data.where_veritas_loses || [])
    .map((l) => `<li>${escapeHTML(l)}</li>`)
    .join("");
  els.scorecardContent.innerHTML = `
    <table class="metric-table">
      <thead><tr><th>Metric</th><th>VERITAS</th><th>Single Prompt</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${losses ? `<div class="losses-block"><h3>Where VERITAS loses</h3><ul>${losses}</ul></div>` : ""}
  `;
}

/* init */
renderChips();
renderNodeSpine();
