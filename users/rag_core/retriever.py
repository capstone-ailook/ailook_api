"""Qdrant pre-filter + vector search."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue


@dataclass
class RetrievedOutfit:
    image: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def retrieve(
    client: QdrantClient,
    collection: str,
    query_vector: list[float],
    gender: str,
    substyle: str | None,
    top_k: int = 5,
) -> list[RetrievedOutfit]:
    conditions = []
    if gender != "any":
        conditions.append(FieldCondition(key="gender", match=MatchValue(value=gender)))
    if substyle:
        conditions.append(FieldCondition(key="substyle", match=MatchValue(value=substyle)))

    flt = Filter(must=conditions) if conditions else None

    result = client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=flt,
        limit=top_k,
        with_payload=True,
    )

    return [
        RetrievedOutfit(
            image=h.payload.get("image", ""),
            score=h.score,
            metadata=h.payload,
        )
        for h in result.points
    ]
