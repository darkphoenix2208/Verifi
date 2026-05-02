"""
ml/citation_guard.py — Deterministic Citation Guardrail

Enforces the "No Evidence, No Talk" rule by scanning LLM output
for [Source: ID] tags and verifying each against a whitelist
of valid evidence IDs.

Author: darkphoenix2208
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# Regex to capture citation tags like [Source: TC-001] or [Source: EMP-1001]
_CITATION_RE = re.compile(r"\[Source:\s*([^\]]+)\]", re.IGNORECASE)


def verify_citations(
    generated_text: str,
    valid_ids: List[str],
) -> Dict[str, Any]:
    """Scan generated text for citation tags and verify each against valid IDs.

    Parameters
    ----------
    generated_text : str
        LLM-generated text (e.g. a SAR report) that may contain
        inline citations like ``[Source: TC-001]``.
    valid_ids : list[str]
        Whitelist of evidence/source IDs that actually exist in
        the investigation state.

    Returns
    -------
    dict
        {
            "citation_passed": bool,
            "total_citations": int,
            "valid_citations": [str, ...],
            "invalid_citations": [str, ...],
            "uncited": bool,  # True if text has zero citations
        }
    """
    if not generated_text or not isinstance(generated_text, str):
        return {
            "citation_passed": False,
            "total_citations": 0,
            "valid_citations": [],
            "invalid_citations": [],
            "uncited": True,
        }

    valid_set = {v.strip().upper() for v in (valid_ids or [])}

    found = _CITATION_RE.findall(generated_text)
    cited_ids = [c.strip() for c in found]

    valid_found = [c for c in cited_ids if c.upper() in valid_set]
    invalid_found = [c for c in cited_ids if c.upper() not in valid_set]

    uncited = len(cited_ids) == 0
    passed = len(invalid_found) == 0 and not uncited

    return {
        "citation_passed": passed,
        "total_citations": len(cited_ids),
        "valid_citations": valid_found,
        "invalid_citations": invalid_found,
        "uncited": uncited,
    }
