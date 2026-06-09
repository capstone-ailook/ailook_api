"""BGE-M3 임베딩 래퍼 — sentence-transformers 로컬 실행 버전.

외부 API(HuggingFace Inference API) 의존을 제거하고 서버 내에서 직접 모델을 실행합니다.
모델은 최초 실행 시 HuggingFace Hub에서 다운로드되어 캐시됩니다.
"""
from __future__ import annotations

from functools import lru_cache

# paraphrase-multilingual-MiniLM-L12-v2: 한국어 지원 + ~400MB (Render 무료 티어 호환)
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache(maxsize=1)
def _model():
    """SentenceTransformer 모델을 최초 1회만 로드하고 이후 캐싱합니다."""
    from sentence_transformers import SentenceTransformer
    print(f"[Embedder] Loading model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"[Embedder] Model loaded successfully.")
    return model


def encode(text: str) -> list[float]:
    return encode_batch([text])[0]


def encode_batch(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    model = _model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,  # 코사인 유사도 최적화
        show_progress_bar=False,
    )
    return embeddings.tolist()
