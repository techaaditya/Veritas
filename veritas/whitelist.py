"""
Domain whitelist for evidence retrieval.

This is a substantive design decision, not plumbing: VERITAS only ever grounds
claims in sources from this list. If a domain (health/legal/agriculture)
question has zero whitelisted evidence, the claim is marked NO_EVIDENCE and
passed forward honestly rather than falling back to open web search. Refusing
to fall back is the point of the system — a general search would reintroduce
exactly the unverified-source problem this pipeline exists to eliminate.
"""

WHITELIST: dict[str, list[str]] = {
    "health": [
        "who.int",
        "dda.gov.np",
        "mohp.gov.np",
        "nhrc.gov.np",
        "ncbi.nlm.nih.gov",
        "cdc.gov",
        "nice.org.uk",
    ],
    "legal": [
        "lawcommission.gov.np",
        "moljpa.gov.np",
        "supremecourt.gov.np",
    ],
    "agriculture": [
        "fao.org",
        "moald.gov.np",
        "narc.gov.np",
    ],
}


def domains_for(domain: str) -> list[str]:
    """Return the whitelisted source domains for a question domain.

    Unknown/"other" domains get an empty whitelist by design — VERITAS has
    no authoritative sources configured for them, so every claim in that
    domain will correctly resolve to NO_EVIDENCE rather than searching openly.
    """
    return WHITELIST.get(domain, [])
