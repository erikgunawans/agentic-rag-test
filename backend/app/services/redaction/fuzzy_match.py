"""Algorithmic Jaro-Winkler fuzzy matching for de-anonymization (D-67/D-68/D-70).

Why this exists:
- Phase 4 Pass 2 of the placeholder-tokenized de-anon pipeline scans the
  remaining (post-Pass 1) text for slightly-mangled surrogate forms ("M. Smyth"
  for canonical "Marcus Smith"). Pure-Python Jaro-Winkler is ~50x slower
  at warm-path scale, so we use rapidfuzz's C-extension implementation
  (already a transitive Presidio dep — no new top-level dependency).
- Per-cluster scoping (D-68): we ONLY score against variants in this thread's
  registry. Cross-cluster scoring would risk merging two distinct people
  whose surrogate names happen to be similar.

Pre-fuzzy normalization (D-70):
    1. Strip honorifics via Phase 1's honorifics.strip_honorific (Pak / Bu / etc.).
    2. casefold both strings (Phase 2 D-36 invariant; Phase 3 D-53 egress filter consistency).
    3. Token-level scoring: split into whitespace tokens; score each (a, b)
       pair; take max.

No @traced decorator — pure CPU function called from de_anonymize_text which
is already @traced(name="redaction.de_anonymize_text"). Span attributes get
added at the caller (Plan 04-03).
"""
from __future__ import annotations

from rapidfuzz.distance import JaroWinkler

from app.services.redaction.honorifics import strip_honorific


def _normalize_for_fuzzy(s: str) -> list[str]:
    """D-70 normalization: strip honorific + casefold + tokenize on whitespace.

    Returns an empty list when the input is empty or contains only honorific
    + whitespace (e.g., 'Pak ' alone normalizes to []).
    """
    if not s:
        return []
    _honorific, bare = strip_honorific(s)
    return bare.casefold().split()


def fuzzy_score(candidate: str, variant: str) -> float:
    """Jaro-Winkler similarity in [0.0, 1.0] after D-70 normalization.

    Token-level: max-over-pairs to catch "John A. Smith" vs "John Smith" and
    "M. Smyth" vs "Marcus Smith". Returns 0.0 if either side normalizes to
    no tokens (empty input or honorific-only).
    """
    cand_tokens = _normalize_for_fuzzy(candidate)
    var_tokens = _normalize_for_fuzzy(variant)
    if not cand_tokens or not var_tokens:
        return 0.0
    return max(
        JaroWinkler.normalized_similarity(c, v)
        for c in cand_tokens
        for v in var_tokens
    )


def best_match(
    candidate: str,
    variants: list[str],
    threshold: float = 0.85,
) -> tuple[str, float] | None:
    """D-67/D-68: return (best_variant, score) if best score >= threshold; else None.

    Per-cluster scoping is the CALLER's responsibility (D-68) — pass only
    this cluster's variants to keep matches privacy-correct. The function
    does NOT cross-reference any registry; it is a pure transform.
    """
    if not variants:
        return None
    best_var = max(variants, key=lambda v: fuzzy_score(candidate, v))
    best_score = fuzzy_score(candidate, best_var)
    if best_score >= threshold:
        return best_var, best_score
    return None
