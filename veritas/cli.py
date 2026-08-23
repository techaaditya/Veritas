"""End-to-end CLI: runs a question through the full N1..N9 pipeline, printing
each node's event live and writing the full trace to logs/<run_id>.json."""
import asyncio
import io
import json
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from veritas.orchestrator import run_stream


async def main(question: str) -> None:
    print(f"QUESTION: {question}\n")
    async for event in run_stream(question):
        if event.type in ("node_start", "node_done", "arbiter", "halt", "error"):
            print(f"--- [{event.type}] {event.node or ''} ---")
            print(json.dumps(event.data, ensure_ascii=False, indent=2)[:2000])
            print()
        elif event.type == "claim_update":
            print(f"[claim_update] {event.node} -> {json.dumps(event.data, ensure_ascii=False)}")
        elif event.type == "final":
            print("=== FINAL ===")
            print(f"run_id:   {event.data['run_id']}")
            print(f"tier:     {event.data['tier']}")
            print(f"decision: {event.data['decision']}")
            print(f"cost:     ${event.data['total_cost_usd']:.6f}")
            print(f"latency:  {event.data['total_latency_ms']:.0f} ms")
            if event.data["degraded_nodes"]:
                print(f"degraded: {event.data['degraded_nodes']}")
            print(f"\n{event.data['response_text']}")


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "बच्चालाई ज्वरो आयो, प्यारासिटामोल कति दिने?"
    asyncio.run(main(q))
