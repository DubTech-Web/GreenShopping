"""Lightweight recommendation engine (Spec §10, §19).

A DETERMINISTIC, EXPLAINABLE weighted-scoring algorithm — not machine learning, and never an
external AI/LLM call (Spec §19). Every recommendation carries a plain-language reason.

    score(candidate | seed) =
        0.40 * relevance          # price proximity + name/description token overlap
      + 0.30 * category_similarity # 1.0 same category as seed, else 0.0
      + 0.30 * sustainability      # eco_score/100, with a bonus when greener than the seed

Design notes (green + honest):
- The candidate pool passed in is the seed's own category (an indexed query in the router),
  so category_similarity is effectively constant there; relevance and sustainability do the
  ranking. The term is still computed generically so cross-category pools also work.
- "Customer purchase history" (Spec §10 input) is applied by EXCLUDING already-purchased
  products via `exclude_ids` — real personalization with no extra writes (Spec §16).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Product

W_RELEVANCE = 0.40
W_CATEGORY = 0.30
W_SUSTAINABILITY = 0.30

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ScoredProduct:
    product: Product
    score: float
    reason: str


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _relevance(seed: Product, cand: Product) -> float:
    """0..1 from name/description token overlap (Jaccard) and price proximity."""
    seed_tokens = _tokens(f"{seed.name} {seed.description}")
    cand_tokens = _tokens(f"{cand.name} {cand.description}")
    if seed_tokens and cand_tokens:
        overlap = len(seed_tokens & cand_tokens) / len(seed_tokens | cand_tokens)
    else:
        overlap = 0.0

    hi = max(float(seed.price), float(cand.price), 1.0)
    price_proximity = 1.0 - abs(float(seed.price) - float(cand.price)) / hi
    return round(0.6 * overlap + 0.4 * price_proximity, 4)


def _category_similarity(seed: Product, cand: Product) -> float:
    return 1.0 if cand.category == seed.category else 0.0


def _sustainability(seed: Product, cand: Product) -> float:
    """eco_score normalized to 0..1, plus a small bonus when cleaner than the seed."""
    base = max(0, min(cand.eco_score, 100)) / 100.0
    greener_bonus = 0.1 if cand.carbon_factor < seed.carbon_factor else 0.0
    return round(min(base + greener_bonus, 1.0), 4)


def _score(seed: Product, cand: Product) -> float:
    return round(
        W_RELEVANCE * _relevance(seed, cand)
        + W_CATEGORY * _category_similarity(seed, cand)
        + W_SUSTAINABILITY * _sustainability(seed, cand),
        4,
    )


def _reason(seed: Product, cand: Product) -> str:
    bits: list[str] = []
    if cand.category == seed.category:
        bits.append(f"same category ({cand.category})")
    if cand.eco_score >= seed.eco_score:
        bits.append(f"higher eco score ({cand.eco_score} vs {seed.eco_score})")
    if cand.carbon_factor < seed.carbon_factor:
        bits.append("lower estimated carbon impact")
    if not bits:
        bits.append("related product")
    return "Recommended because it is " + ", ".join(bits) + "."


def recommend_similar(
    seed: Product,
    candidates: list[Product],
    *,
    limit: int = 4,
    exclude_ids: set[int] = frozenset(),
) -> list[ScoredProduct]:
    """Top-`limit` similar products, highest score first, each with an explanation."""
    scored = [
        ScoredProduct(product=c, score=_score(seed, c), reason=_reason(seed, c))
        for c in candidates
        if c.id != seed.id and c.id not in exclude_ids
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


def find_eco_alternative(seed: Product, candidates: list[Product]) -> ScoredProduct | None:
    """Best strictly-greener same-category product: higher eco_score AND lower carbon (§10B)."""
    greener = [
        c
        for c in candidates
        if c.id != seed.id
        and c.category == seed.category
        and c.eco_score > seed.eco_score
        and c.carbon_factor < seed.carbon_factor
    ]
    if not greener:
        return None
    best = max(greener, key=lambda c: (c.eco_score, -c.carbon_factor))
    reason = (
        f"Greener alternative to {seed.name}: eco score {best.eco_score} vs {seed.eco_score} "
        f"and lower estimated carbon impact, in the same category."
    )
    return ScoredProduct(product=best, score=_score(seed, best), reason=reason)
