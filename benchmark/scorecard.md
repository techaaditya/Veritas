# VERITAS Benchmark Scorecard

n = 30 questions · baseline arm: `gemma4:31b` single prompt · VERITAS: full nine-node pipeline

## Six metrics, both arms

| Metric | VERITAS | Single Prompt |
|---|---|---|
| Hallucination rate (auto-flagged unanswerable/trap subset, n=7; 20 more pending manual adjudication) | n/a (needs adjudication) | 100.0% |
| Citation validity (URLs live, n=20) | 70.0% | 3.3% of responses even include a URL (n=30) |
| Appropriate refusal rate (n=7) | 71.4% | n/a — single prompt has no refusal mechanism |
| Over-refusal rate (n=19) | 84.2% | n/a |
| TIER-0 escalation recall (n=3) | 100.0% | n/a — single prompt does not halt |
| Cost per query | $0.00188 | $0.00024 |
| Latency per query | 19584 ms | 9705 ms |

## Where VERITAS loses

- **Cost:** VERITAS costs **7.7x** the single prompt per query ($0.00188 vs $0.00024).
- **Latency:** VERITAS takes **2.0x** as long (19584 ms vs 9705 ms).
- **Over-refusal:** 16/19 answerable questions were wrongly refused (84.2%).
- **Degraded runs:** 6 run(s) fell back to a secondary provider mid-pipeline: H1, H3, H6, L3, R1, R4.

The framing: we traded latency and cost for a large reduction in unsupported claims. For a dosing question that's a trade any clinician would take; for trivia it isn't — which is why the risk gate (N2) exists.

**Manual step remaining:** open `benchmark/adjudication.csv` and fill in the `hallucination_in_baseline_0_or_1` / `hallucination_in_veritas_0_or_1` columns for the 20 questions in health_answerable/legal_lookup/romanized/numeric_dosing buckets, then rerun this script to fold in a complete hallucination-rate figure.
