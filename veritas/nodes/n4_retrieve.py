"""
N4 — Evidence Retrieval. Not an LLM node: Firecrawl for live site-restricted
search + scrape, with a local corpus fallback so a Firecrawl outage or missing
key cannot take the pipeline down.

For each claim, we search only within that domain's whitelisted sources
(`veritas.whitelist`), scrape the top results, and chunk them. If Firecrawl is
unavailable or returns nothing, we fall back to `corpus/<domain>.json` — a
small hand-curated set of real, verbatim, source-attributed extracts. If
neither produces anything, the claim is honestly marked NO_EVIDENCE. VERITAS
never falls back to open/unrestricted web search — that would defeat the
purpose of the whitelist.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from veritas.whitelist import domains_for

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "retrieval"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus"
CHUNK_CHARS = 1200


@dataclass
class EvidenceChunk:
    url: str
    retrieved_at: str
    text: str
    source: str  # "firecrawl" | "corpus"


@dataclass
class RetrievalResult:
    claim_id: str
    status: str  # "OK" | "NO_EVIDENCE"
    chunks: list[EvidenceChunk] = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None


def _cache_key(claim_question: str, domain: str) -> str:
    h = hashlib.sha256()
    h.update(f"{claim_question}|{domain}".encode("utf-8"))
    return h.hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _read_cache(key: str) -> list[dict] | None:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _write_cache(key: str, chunks: list[dict]) -> None:
    _cache_path(key).write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")


def _chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


def _firecrawl_search(claim_question: str, search_terms: list[str], allowed_domains: list[str]) -> list[EvidenceChunk]:
    from firecrawl import Firecrawl
    from firecrawl.v2.types import ScrapeOptions

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY not set")

    client = Firecrawl(api_key=api_key)
    query = claim_question if not search_terms else f"{claim_question} {' '.join(search_terms)}"

    result = client.search(
        query,
        include_domains=allowed_domains,
        limit=3,
        scrape_options=ScrapeOptions(formats=["markdown"], only_main_content=True),
    )

    chunks: list[EvidenceChunk] = []
    web_results = getattr(result, "web", None) or []
    retrieved_at = time.strftime("%Y-%m-%d")
    for item in web_results[:3]:
        metadata = getattr(item, "metadata", None)
        url = getattr(metadata, "url", None) if metadata else None
        title = (getattr(metadata, "title", None) or "") if metadata else ""
        markdown = getattr(item, "markdown", None)
        if not url or not markdown:
            continue
        if "recaptcha" in title.lower() or "checking your browser" in markdown[:200].lower():
            continue
        for piece in _chunk_text(markdown)[:2]:
            chunks.append(EvidenceChunk(url=url, retrieved_at=retrieved_at, text=piece, source="firecrawl"))
    return chunks


_corpus_cache: dict[str, list[dict]] = {}


def _load_corpus(domain: str) -> list[dict]:
    if domain in _corpus_cache:
        return _corpus_cache[domain]
    path = CORPUS_DIR / f"{domain}.json"
    if not path.exists():
        _corpus_cache[domain] = []
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    _corpus_cache[domain] = entries
    return entries


def _corpus_search(claim_question: str, search_terms: list[str], domain: str) -> list[EvidenceChunk]:
    entries = _load_corpus(domain)
    if not entries:
        return []

    needle_words = {w.lower() for w in (search_terms + claim_question.split()) if len(w) > 2}
    scored: list[tuple[int, dict]] = []
    for entry in entries:
        tag_words = {t.lower() for t in entry.get("tags", [])}
        text_words = {w.lower().strip(".,()") for w in entry.get("text", "").split()}
        overlap = len(needle_words & tag_words) * 3 + len(needle_words & text_words)
        if overlap > 0:
            scored.append((overlap, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    chunks = []
    for _, entry in scored[:3]:
        chunks.append(
            EvidenceChunk(
                url=entry["url"],
                retrieved_at=entry["retrieved_at"],
                text=entry["text"],
                source="corpus",
            )
        )
    return chunks


def retrieve_for_claim(claim_id: str, claim_question: str, search_terms: list[str], domain: str) -> RetrievalResult:
    allowed_domains = domains_for(domain)
    if not allowed_domains:
        return RetrievalResult(claim_id=claim_id, status="NO_EVIDENCE")

    key = _cache_key(claim_question, domain)
    cached = _read_cache(key)
    if cached is not None:
        chunks = [EvidenceChunk(**c) for c in cached]
        return RetrievalResult(
            claim_id=claim_id,
            status="OK" if chunks else "NO_EVIDENCE",
            chunks=chunks,
        )

    degraded = False
    degraded_reason = None
    chunks: list[EvidenceChunk] = []
    try:
        chunks = _firecrawl_search(claim_question, search_terms, allowed_domains)
    except Exception as e:  # noqa: BLE001 - Firecrawl outage must not crash the pipeline
        degraded = True
        degraded_reason = f"Firecrawl unavailable ({e}); used local corpus fallback"

    if not chunks:
        chunks = _corpus_search(claim_question, search_terms, domain)
        if chunks and not degraded:
            degraded = True
            degraded_reason = "Firecrawl returned no whitelisted results; used local corpus fallback"

    if chunks:
        _write_cache(key, [c.__dict__ for c in chunks])

    return RetrievalResult(
        claim_id=claim_id,
        status="OK" if chunks else "NO_EVIDENCE",
        chunks=chunks,
        degraded=degraded,
        degraded_reason=degraded_reason,
    )
