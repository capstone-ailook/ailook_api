"""BGE-M3 임베딩 래퍼 — 모듈 레벨 singleton (첫 호출 시 로드)."""
from __future__ import annotations

_model = None


def _get_model():
    global _model
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    return _model


def encode(text: str) -> list[float]:
    result = _get_model().encode([text], batch_size=1, max_length=512)
    return result["dense_vecs"][0].tolist()


def encode_batch(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    result = _get_model().encode(texts, batch_size=batch_size, max_length=512)
    return [v.tolist() for v in result["dense_vecs"]]
