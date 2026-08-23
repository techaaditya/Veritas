"""
VERITAS web server — serves the split-screen comparison UI and streams both
arms (baseline single-prompt vs. the full nine-node pipeline) over SSE so the
frontend can render them racing live, side by side.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from veritas import baseline
from veritas.orchestrator import run_stream

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
BENCHMARK_DIR = ROOT / "benchmark"

app = FastAPI(title="VERITAS")


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/veritas")
async def api_veritas(q: str = Query(..., min_length=1)):
    async def gen():
        try:
            async for event in run_stream(q):
                yield _sse(event.type, event.to_json())
        except Exception as e:  # noqa: BLE001 - stream must close cleanly even on unexpected failure
            yield _sse("error", {"reason": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/baseline")
async def api_baseline(q: str = Query(..., min_length=1)):
    async def gen():
        try:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue = asyncio.Queue()

            def produce():
                try:
                    for chunk in baseline.run_stream(q):
                        loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
                except Exception as e:  # noqa: BLE001
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

            asyncio.get_event_loop().run_in_executor(None, produce)

            while True:
                kind, payload = await queue.get()
                if kind == "chunk":
                    yield _sse("chunk", {"text": payload})
                elif kind == "error":
                    yield _sse("error", {"reason": payload})
                    break
                else:
                    yield _sse("done", {})
                    break
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"reason": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/benchmark")
async def api_benchmark():
    scorecard_path = BENCHMARK_DIR / "scorecard.json"
    if not scorecard_path.exists():
        return {"available": False}
    return {"available": True, **json.loads(scorecard_path.read_text(encoding="utf-8"))}


@app.get("/api/examples")
async def api_examples():
    path = BENCHMARK_DIR / "demo_examples.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
