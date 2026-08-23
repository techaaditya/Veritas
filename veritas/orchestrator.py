"""
Orchestrator — runs N1..N9 as an async pipeline, emitting a stream of events
(consumed live by the web UI over SSE, and by the CLI/benchmark for a final
result) and writing every node's raw input/output to logs/<run_id>.json.

Control flow, not a straight chain:
  - N2 TIER_0 halts the pipeline immediately and returns an escalation card.
  - N4/N5/N6 fan out per-claim, bounded by a concurrency semaphore.
  - N9 -> N8 retries once on fidelity drift, then degrades to a bilingual
    side-by-side response rather than silently shipping a drifted translation.
  - A 90s global timeout preserves whatever partial result exists so far.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

from veritas.clients import LLMResult
from veritas.nodes import (
    n1_normalize,
    n2_risk_gate,
    n3_decompose,
    n4_retrieve,
    n5_answer,
    n6_verify,
    n8_synthesize,
    n9_fidelity,
)
from veritas.nodes.n7_arbiter import ChallengeResult, ClaimResult, arbitrate

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

GLOBAL_TIMEOUT_S = 180  # generous enough to absorb one real rate-limit wait on Gemini's free tier (5 req/min)
CLAIM_CONCURRENCY = 2  # lower burst pressure against that same per-minute quota

EMERGENCY_CARD = {
    "ne": {
        "heading": "⚠ यो आपतकालीन अवस्था हुन सक्छ",
        "body": "यो प्रश्नले चिकित्सकीय आपतकालीन अवस्थाको संकेत गर्छ। कृपया तुरुन्त नजिकैको अस्पताल जानुहोस् वा तल दिइएको नम्बरमा फोन गर्नुहोस्। यो प्रणालीले जानकारीमूलक उत्तर दिँदैन किनभने ढिलाइ खतरनाक हुन सक्छ।",
        "contacts": ["प्रहरी: १००", "एम्बुलेन्स / स्वास्थ्य आपतकाल: १०२", "राष्ट्रिय आपतकालीन नम्बर: ११४५"],
    },
    "en": {
        "heading": "⚠ This may be a medical emergency",
        "body": "This question indicates a possible in-progress medical emergency. Please go to the nearest hospital or call emergency services immediately. This system will not attempt an informational answer because delay could be dangerous.",
        "contacts": ["Police: 100", "Ambulance / Health Emergency: 102", "National Emergency Hotline: 1145"],
    },
}


@dataclass
class NodeEvent:
    type: str  # node_start | node_done | claim_update | arbiter | halt | final | error
    node: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        return {"type": self.type, "node": self.node, "data": self.data, "ts": self.ts}


@dataclass
class VeritasRun:
    run_id: str
    question: str
    tier: str | None = None
    domain: str | None = None
    detected_language: str | None = None
    decision: str | None = None
    response_text: str | None = None
    citations: list = field(default_factory=list)
    claims: list = field(default_factory=list)
    node_log: list = field(default_factory=list)  # raw I/O per node call
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    degraded_nodes: list = field(default_factory=list)
    halted: bool = False
    halt_reason: str | None = None
    timed_out: bool = False

    def to_json(self) -> dict:
        return asdict(self)


def _claims_summary_text(claims: list[dict]) -> str:
    lines = []
    for c in claims:
        lines.append(
            f"[{c['id']}] ({c['criticality']}) Q: {c['claim_question']}\n"
            f"  verdict={c['verdict']} answer={c.get('answer')}\n"
            f"  evidence_span={c.get('evidence_span')}\n"
            f"  source={c.get('source_url')}\n"
            f"  caveats={c.get('caveats', [])}\n"
            f"  challenge={c.get('challenge')}"
        )
    return "\n".join(lines) if lines else "(no claims)"


def _record(run: VeritasRun, result: LLMResult) -> None:
    run.total_cost_usd += result.cost_usd
    run.total_latency_ms += result.latency_ms
    if result.degraded and result.node not in run.degraded_nodes:
        run.degraded_nodes.append(result.node)
    run.node_log.append(
        {
            "node": result.node,
            "provider": result.provider,
            "model": result.model,
            "prompt": result.prompt,
            "raw_response": result.raw_text,
            "parsed": result.data,
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost_usd": result.cost_usd,
            "cached": result.cached,
            "degraded": result.degraded,
            "degraded_reason": result.degraded_reason,
        }
    )


async def _call(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


async def _process_claim(run: VeritasRun, claim: dict, domain: str, sem: asyncio.Semaphore) -> AsyncIterator[NodeEvent]:
    claim_id = claim["id"]
    async with sem:
        retrieval = await _call(
            n4_retrieve.retrieve_for_claim, claim_id, claim["claim_question"], claim.get("search_terms", []), domain
        )
        yield NodeEvent(
            "claim_update",
            "N4",
            {
                "claim_id": claim_id,
                "status": retrieval.status,
                "sources": [c.url for c in retrieval.chunks],
                "degraded": retrieval.degraded,
                "degraded_reason": retrieval.degraded_reason,
            },
        )

        if retrieval.status == "NO_EVIDENCE":
            claim.update(
                verdict="UNSUPPORTED",
                answer=None,
                evidence_span=None,
                source_url=None,
                caveats=["no whitelisted evidence found for this claim"],
                challenge=None,
            )
            yield NodeEvent("claim_update", "N5", {"claim_id": claim_id, "verdict": "UNSUPPORTED", "skipped": True})
            return

        n5_result = await _call(n5_answer.run, claim_id, claim["claim_question"], retrieval.chunks)
        _record(run, n5_result)
        d = n5_result.data
        claim.update(
            verdict=d.get("verdict", "UNSUPPORTED"),
            answer=d.get("answer"),
            evidence_span=d.get("evidence_span"),
            source_url=d.get("source_url"),
            caveats=d.get("caveats", []),
        )
        yield NodeEvent("claim_update", "N5", {"claim_id": claim_id, "verdict": claim["verdict"], "answer": claim["answer"]})

        if claim["verdict"] in ("UNSUPPORTED", "CONTRADICTED") and not claim.get("evidence_span"):
            claim["challenge"] = None
            return

        n6_result = await _call(
            n6_verify.run, claim_id, claim["claim_question"], claim.get("answer"), claim.get("evidence_span"), claim.get("source_url")
        )
        _record(run, n6_result)
        cd = n6_result.data
        claim["challenge"] = {
            "verdict_after_challenge": cd.get("verdict_after_challenge", "HOLDS"),
            "flags": cd.get("flags", ["NONE"]),
            "falsification_attempt": cd.get("falsification_attempt"),
            "confidence": cd.get("confidence"),
        }
        yield NodeEvent("claim_update", "N6", {"claim_id": claim_id, **claim["challenge"]})


async def run_stream(question: str) -> AsyncIterator[NodeEvent]:
    run = VeritasRun(run_id=uuid.uuid4().hex[:12], question=question)
    start_time = time.monotonic()

    try:
        async with asyncio.timeout(GLOBAL_TIMEOUT_S):
            # --- N1 ---
            yield NodeEvent("node_start", "N1", {"question": question})
            n1 = await _call(n1_normalize.run, question)
            _record(run, n1)
            run.detected_language = n1.data.get("detected_language")
            run.domain = n1.data.get("domain")
            yield NodeEvent("node_done", "N1", n1.data)

            # --- N2 ---
            yield NodeEvent("node_start", "N2", {})
            n2 = await _call(
                n2_risk_gate.run, n1.data["canonical_english"], question, n1.data.get("domain", "other")
            )
            _record(run, n2)
            run.tier = n2.data.get("tier")
            yield NodeEvent("node_done", "N2", n2.data)

            if run.tier == "TIER_0":
                lang = "ne" if run.detected_language in ("ne", "ne-Latn", "mixed") else "en"
                card = EMERGENCY_CARD[lang]
                run.halted = True
                run.halt_reason = n2.data.get("reasoning")
                run.decision = "HALT"
                run.response_text = card["body"]
                run.citations = []
                yield NodeEvent(
                    "halt",
                    "N2",
                    {
                        "card": card,
                        "emergency_signals": n2.data.get("emergency_signals", []),
                        "reasoning": run.halt_reason,
                    },
                )
                run.total_latency_ms = (time.monotonic() - start_time) * 1000
                _write_log(run)
                yield NodeEvent("final", None, run.to_json())
                return

            # --- N3 ---
            yield NodeEvent("node_start", "N3", {})
            n3 = await _call(n3_decompose.run, n1.data["canonical_english"], n1.data.get("entities", []), run.domain)
            _record(run, n3)
            claims: list[dict] = n3.data.get("claims", [])
            yield NodeEvent("node_done", "N3", {"claims": claims})

            # --- N4/N5/N6 fan-out per claim ---
            sem = asyncio.Semaphore(CLAIM_CONCURRENCY)

            async def drive_claim(c: dict) -> AsyncIterator[NodeEvent]:
                async for ev in _process_claim(run, c, run.domain, sem):
                    yield ev

            queues: list[asyncio.Queue] = []
            tasks = []
            for c in claims:
                q: asyncio.Queue = asyncio.Queue()
                queues.append(q)

                async def pump(claim=c, queue=q):
                    async for ev in drive_claim(claim):
                        await queue.put(ev)
                    await queue.put(None)

                tasks.append(asyncio.create_task(pump()))

            active = len(queues)
            while active > 0:
                for q in queues:
                    try:
                        ev = q.get_nowait()
                    except asyncio.QueueEmpty:
                        continue
                    if ev is None:
                        active -= 1
                        continue
                    yield ev
                await asyncio.sleep(0.02)
            await asyncio.gather(*tasks)

            # --- N7 arbiter (deterministic) ---
            claim_results = [
                ClaimResult(
                    id=c["id"],
                    criticality=c.get("criticality", "supporting"),
                    verdict=c.get("verdict", "UNSUPPORTED"),
                    challenge=ChallengeResult(
                        verdict_after_challenge=c["challenge"]["verdict_after_challenge"],
                        flags=c["challenge"]["flags"],
                    )
                    if c.get("challenge")
                    else None,
                )
                for c in claims
            ]
            decision, reasons = arbitrate(run.tier, claim_results)
            run.decision = decision
            run.claims = claims
            yield NodeEvent("arbiter", "N7", {"decision": decision, "reasons": reasons})

            # --- N8 synthesize, N9 fidelity (one retry on drift) ---
            claims_text = _claims_summary_text(claims)
            yield NodeEvent("node_start", "N8", {})
            n8 = await _call(n8_synthesize.run, run.detected_language or "en", decision, claims_text)
            _record(run, n8)
            response_text = n8.data.get("response_text", "")
            citations = n8.data.get("citations", [])
            yield NodeEvent("node_done", "N8", {"response_text": response_text, "citations": citations})

            yield NodeEvent("node_start", "N9", {})
            n9 = await _call(n9_fidelity.run, response_text, claims_text)
            _record(run, n9)
            fidelity_ok = n9.data.get("fidelity_ok", True)
            yield NodeEvent("node_done", "N9", n9.data)

            if not fidelity_ok:
                drift_note = json.dumps(n9.data.get("drift", []), ensure_ascii=False)
                yield NodeEvent("node_start", "N8", {"retry": True, "drift": n9.data.get("drift", [])})
                n8_retry = await _call(
                    n8_synthesize.run, run.detected_language or "en", decision, claims_text, drift_note
                )
                _record(run, n8_retry)
                response_text_retry = n8_retry.data.get("response_text", "")
                citations_retry = n8_retry.data.get("citations", [])
                yield NodeEvent("node_done", "N8", {"response_text": response_text_retry, "citations": citations_retry, "retry": True})

                n9_retry = await _call(n9_fidelity.run, response_text_retry, claims_text)
                _record(run, n9_retry)
                yield NodeEvent("node_done", "N9", {**n9_retry.data, "retry": True})

                if n9_retry.data.get("fidelity_ok", True):
                    response_text, citations = response_text_retry, citations_retry
                else:
                    run.degraded_nodes.append("N9")
                    response_text = (
                        f"{response_text_retry}\n\n---\n[Fidelity check could not be satisfied after retry; "
                        f"showing the verified English claim summary alongside the translation for safety.]\n\n{claims_text}"
                    )
                    citations = citations_retry

            run.response_text = response_text
            run.citations = citations

            run.total_latency_ms = (time.monotonic() - start_time) * 1000
            _write_log(run)
            yield NodeEvent("final", None, run.to_json())

    except TimeoutError:
        run.timed_out = True
        run.total_latency_ms = (time.monotonic() - start_time) * 1000
        if run.decision is None:
            run.decision = "REFUSE"
            run.response_text = "The system could not complete verification within the time limit. Please try again or consult a professional directly."
        _write_log(run)
        yield NodeEvent("error", None, {"reason": "timeout", "partial": run.to_json()})
        yield NodeEvent("final", None, run.to_json())
    except Exception as e:  # noqa: BLE001 - a node failure must degrade to an "error" event, never crash the run
        run.total_latency_ms = (time.monotonic() - start_time) * 1000
        _write_log(run)
        yield NodeEvent("error", None, {"reason": str(e), "partial": run.to_json()})
        yield NodeEvent("final", None, run.to_json())


def _write_log(run: VeritasRun) -> None:
    path = LOGS_DIR / f"{run.run_id}.json"
    path.write_text(json.dumps(run.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")


async def run(question: str) -> VeritasRun:
    """Drain the event stream and return the final VeritasRun (for CLI/benchmark callers)."""
    final: VeritasRun | None = None
    async for event in run_stream(question):
        if event.type == "final":
            final = VeritasRun(**event.data)
    assert final is not None
    return final
