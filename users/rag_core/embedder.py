"""BGE-M3 임베딩 래퍼 — Hugging Face Inference API를 사용한 경량화 버전."""
from __future__ import annotations

import os
import time
import requests
from django.conf import settings

API_URL = "https://api-inference.huggingface.co/models/BAAI/bge-m3"


def _get_headers() -> dict[str, str]:
    try:
        token = getattr(settings, "HF_TOKEN", None)
    except Exception:
        token = os.environ.get("HF_TOKEN")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def encode(text: str) -> list[float]:
    return encode_batch([text])[0]


def encode_batch(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    headers = _get_headers()
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json={"inputs": texts},
                timeout=30
            )
            
            # API 호출이 성공한 경우
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    # 3D response: [batch, seq_len, dim] -> Mean Pooling 수행
                    if isinstance(result[0], list) and len(result[0]) > 0 and isinstance(result[0][0], list):
                        pooled = []
                        for seq in result:
                            dim = len(seq[0])
                            avg_vec = [0.0] * dim
                            for token_vec in seq:
                                for i, val in enumerate(token_vec):
                                    avg_vec[i] += val
                            avg_vec = [v / len(seq) for v in avg_vec]
                            pooled.append(avg_vec)
                        return pooled
                    
                    # 2D response: [batch, dim]
                    if isinstance(result[0], list):
                        return [[float(x) for x in vec] for vec in result]
                
                raise ValueError(f"Unexpected HF response format: {result}")
            
            # 모델이 로딩 중인 경우 (503 Service Unavailable 및 estimated_time 반환)
            if response.status_code == 503:
                try:
                    err_json = response.json()
                    if "is currently loading" in err_json.get("error", ""):
                        wait_time = min(err_json.get("estimated_time", 10.0), 10.0)
                        print(f"[Embedder] Model is loading. Waiting {wait_time}s (attempt {attempt + 1}/{max_attempts})...")
                        time.sleep(wait_time)
                        continue
                except Exception:
                    pass
            
            response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            if attempt == max_attempts - 1:
                raise RuntimeError(f"Failed to fetch embeddings from Hugging Face: {e}") from e
            time.sleep(2)
            
    raise RuntimeError("Failed to get embeddings from Hugging Face Inference API after retries.")

