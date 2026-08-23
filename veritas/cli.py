"""Smoke-test CLI: runs a question through the nodes built so far and prints each JSON."""
import json
import sys

from veritas.nodes import n1_normalize, n2_risk_gate


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "बच्चालाई ज्वरो आयो, प्यारासिटामोल कति दिने?"

    print(f"QUESTION: {question}\n")

    n1 = n1_normalize.run(question)
    print("--- N1 Language & Intent Normalizer ---")
    print(json.dumps(n1.data, ensure_ascii=False, indent=2))
    print(f"(cached={n1.cached}, latency_ms={n1.latency_ms:.0f}, cost_usd={n1.cost_usd:.6f})\n")

    n2 = n2_risk_gate.run(
        canonical_english=n1.data["canonical_english"],
        original_question=question,
        domain=n1.data["domain"],
    )
    print("--- N2 Risk Tier Gate ---")
    print(json.dumps(n2.data, ensure_ascii=False, indent=2))
    print(f"(cached={n2.cached}, latency_ms={n2.latency_ms:.0f}, cost_usd={n2.cost_usd:.6f})\n")

    if n2.data["tier"] == "TIER_0":
        print("!!! TIER_0 — pipeline would HALT here and return an escalation card.")


if __name__ == "__main__":
    main()
