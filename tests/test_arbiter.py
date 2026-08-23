"""
Unit tests for the N7 deterministic refusal arbiter — the most defensible
node in VERITAS. Every branch of arbitrate() is exercised here.
"""
from veritas.nodes.n7_arbiter import ChallengeResult, ClaimResult, arbitrate


def supported(id_="C1", criticality="critical"):
    return ClaimResult(id=id_, criticality=criticality, verdict="SUPPORTED", challenge=ChallengeResult("HOLDS", ["NONE"]))


def unsupported(id_="C1", criticality="critical"):
    return ClaimResult(id=id_, criticality=criticality, verdict="UNSUPPORTED", challenge=ChallengeResult("HOLDS", ["NONE"]))


def contradicted(id_="C1", criticality="critical"):
    return ClaimResult(id=id_, criticality=criticality, verdict="CONTRADICTED", challenge=ChallengeResult("HOLDS", ["NONE"]))


def weakened(id_="C1", criticality="critical"):
    return ClaimResult(id=id_, criticality=criticality, verdict="SUPPORTED", challenge=ChallengeResult("WEAKENED", ["SCOPE_DROPPED"]))


def failed_challenge(id_="C1", criticality="critical"):
    return ClaimResult(id=id_, criticality=criticality, verdict="SUPPORTED", challenge=ChallengeResult("FAILS", ["SPAN_DOES_NOT_ESTABLISH"]))


def number_mismatch(id_="C1", criticality="critical"):
    return ClaimResult(id=id_, criticality=criticality, verdict="SUPPORTED", challenge=ChallengeResult("HOLDS", ["NUMBER_MISMATCH"]))


class TestAnswer:
    def test_all_supported_tier1_answers(self):
        decision, reasons = arbitrate("TIER_1", [supported("C1"), supported("C2")])
        assert decision == "ANSWER"
        assert reasons == []

    def test_all_supported_tier2_answers(self):
        decision, reasons = arbitrate("TIER_2", [supported("C1")])
        assert decision == "ANSWER"

    def test_no_critical_claims_answers(self):
        decision, _ = arbitrate("TIER_1", [supported("C1", "supporting")])
        assert decision == "ANSWER"

    def test_empty_claims_answers(self):
        decision, _ = arbitrate("TIER_1", [])
        assert decision == "ANSWER"


class TestRefuse:
    def test_tier1_unsupported_critical_refuses(self):
        decision, reasons = arbitrate("TIER_1", [unsupported("C1")])
        assert decision == "REFUSE"
        assert "C1" in reasons[0]

    def test_tier1_contradicted_critical_refuses(self):
        decision, reasons = arbitrate("TIER_1", [contradicted("C1")])
        assert decision == "REFUSE"

    def test_tier1_failed_challenge_refuses(self):
        decision, reasons = arbitrate("TIER_1", [failed_challenge("C1")])
        assert decision == "REFUSE"
        assert "adversarial verification" in reasons[0]

    def test_tier1_number_mismatch_refuses(self):
        decision, reasons = arbitrate("TIER_1", [number_mismatch("C1")])
        assert decision == "REFUSE"
        assert "numeric value" in reasons[0]

    def test_tier1_one_bad_claim_among_many_refuses(self):
        decision, reasons = arbitrate("TIER_1", [supported("C1"), unsupported("C2")])
        assert decision == "REFUSE"
        assert any("C2" in r for r in reasons)

    def test_unsupported_supporting_claim_does_not_force_refuse(self):
        # Only critical claims can trigger refusal.
        decision, _ = arbitrate("TIER_1", [supported("C1"), unsupported("C2", "supporting")])
        assert decision == "ANSWER"


class TestPartialAnswer:
    def test_tier1_weakened_gives_partial(self):
        decision, reasons = arbitrate("TIER_1", [weakened("C1")])
        assert decision == "PARTIAL_ANSWER"
        assert "weakened" in reasons[0]

    def test_tier2_unsupported_gives_partial_not_refuse(self):
        # TIER_2 never hard-refuses; only TIER_1 does.
        decision, reasons = arbitrate("TIER_2", [unsupported("C1")])
        assert decision == "PARTIAL_ANSWER"

    def test_tier2_contradicted_gives_partial(self):
        decision, _ = arbitrate("TIER_2", [contradicted("C1")])
        assert decision == "PARTIAL_ANSWER"

    def test_mixed_supported_and_unsupported_tier2(self):
        decision, reasons = arbitrate("TIER_2", [supported("C1"), unsupported("C2")])
        assert decision == "PARTIAL_ANSWER"
        assert any("C2" in r for r in reasons)


class TestDeterminism:
    def test_same_input_same_output(self):
        claims = [supported("C1"), weakened("C2")]
        r1 = arbitrate("TIER_1", claims)
        r2 = arbitrate("TIER_1", claims)
        assert r1 == r2
