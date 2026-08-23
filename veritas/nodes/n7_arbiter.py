"""
N7 — Refusal Arbiter. Pure Python, no LLM.

The decision to refuse is made by code, not by a model. LLMs are unreliable
at consistently applying their own stated policy; moving the refusal rule
into Python makes refusal behaviour auditable, testable, and identical on
every run. This is the single most defensible node in the design.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChallengeResult:
    verdict_after_challenge: str  # "HOLDS" | "WEAKENED" | "FAILS"
    flags: list[str] = field(default_factory=list)


@dataclass
class ClaimResult:
    id: str
    criticality: str  # "critical" | "supporting"
    verdict: str  # "SUPPORTED" | "PARTIAL" | "UNSUPPORTED" | "CONTRADICTED"
    challenge: ChallengeResult | None = None


def arbitrate(tier: str, claims: list[ClaimResult]) -> tuple[str, list[str]]:
    """
    Returns: ("ANSWER" | "PARTIAL_ANSWER" | "REFUSE", reasons)

    Deterministic by design: refusal behaviour must be identical on every
    run and auditable line-by-line. An LLM asked to apply this policy would
    apply it inconsistently.
    """
    critical = [c for c in claims if c.criticality == "critical"]
    reasons: list[str] = []

    for c in critical:
        if c.verdict in ("UNSUPPORTED", "CONTRADICTED"):
            reasons.append(f"{c.id}: critical claim not supported by evidence")
        if c.challenge and c.challenge.verdict_after_challenge == "FAILS":
            reasons.append(f"{c.id}: failed adversarial verification")
        if c.challenge and "NUMBER_MISMATCH" in c.challenge.flags:
            reasons.append(f"{c.id}: numeric value not present in source")

    if tier == "TIER_1" and reasons:
        return "REFUSE", reasons  # high stakes -> no guessing

    if tier == "TIER_1" and any(
        c.challenge and c.challenge.verdict_after_challenge == "WEAKENED" for c in critical
    ):
        return "PARTIAL_ANSWER", ["one or more claims weakened under challenge"]

    if all(c.verdict == "SUPPORTED" for c in critical):
        return "ANSWER", []

    return "PARTIAL_ANSWER", reasons
