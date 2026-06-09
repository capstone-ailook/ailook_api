# """BGE-M3 임베딩 래퍼 — Hugging Face Inference API를 사용한 경량화 버전 (DNS-over-HTTPS 우회 포함)."""
# from __future__ import annotations

# import os
# import time
# import urllib3
# import requests
# from django.conf import settings

# API_URL = "https://api-inference.huggingface.co/models/BAAI/bge-m3"

# # verify=False 사용 시 발생하는 urllib3 경고 비활성화
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# def _get_headers() -> dict[str, str]:
#     try:
#         token = getattr(settings, "HF_TOKEN", None)
#     except Exception:
#         token = os.environ.get("HF_TOKEN")
    
#     headers = {}
#     if token:
#         headers["Authorization"] = f"Bearer {token}"
#     return headers


# def _resolve_dns_over_https(domain: str) -> str | None:
#     """Google 및 Cloudflare Public DoH API를 raw IP로 호출하여 도메인의 IP를 직접 찾습니다.
#     시스템 DNS 서버가 아예 작동하지 않는 상황을 우회합니다.
#     """
#     urls = [
#         f"https://8.8.8.8/resolve?name={domain}&type=A",
#         f"https://1.1.1.1/dns-query?name={domain}&type=A"
#     ]
#     headers = {"accept": "application/dns-json"}
    
#     for url in urls:
#         try:
#             # 8.8.8.8 및 1.1.1.1은 IP 주소이므로 DNS 네임 해석 없이 바로 접속 가능합니다.
#             response = requests.get(url, headers=headers, timeout=5)
#             if response.status_code == 200:
#                 data = response.json()
#                 answers = data.get("Answer", [])
#                 for answer in answers:
#                     if answer.get("type") == 1:  # A 레코드
#                         return answer.get("data")
#         except Exception:
#             continue
#     return None


# def encode(text: str) -> list[float]:
#     return encode_batch([text])[0]


# def _parse_response(response, attempt: int, max_attempts: int) -> list[list[float]]:
#     # API 호출이 성공한 경우
#     if response.status_code == 200:
#         result = response.json()
#         if isinstance(result, list) and len(result) > 0:
#             # 3D response: [batch, seq_len, dim] -> Mean Pooling 수행
#             if isinstance(result[0], list) and len(result[0]) > 0 and isinstance(result[0][0], list):
#                 pooled = []
#                 for seq in result:
#                     dim = len(seq[0])
#                     avg_vec = [0.0] * dim
#                     for token_vec in seq:
#                         for i, val in enumerate(token_vec):
#                             avg_vec[i] += val
#                     avg_vec = [v / len(seq) for v in avg_vec]
#                     pooled.append(avg_vec)
#                 return pooled
            
#             # 2D response: [batch, dim]
#             if isinstance(result[0], list):
#                 return [[float(x) for x in vec] for vec in result]
        
#         raise ValueError(f"Unexpected HF response format: {result}")
    
#     # 모델이 로딩 중인 경우 (503 Service Unavailable 및 estimated_time 반환)
#     if response.status_code == 503:
#         try:
#             err_json = response.json()
#             if "is currently loading" in err_json.get("error", ""):
#                 wait_time = min(err_json.get("estimated_time", 10.0), 10.0)
#                 print(f"[Embedder] Model is loading. Waiting {wait_time}s (attempt {attempt + 1}/{max_attempts})...")
#                 time.sleep(wait_time)
#                 # 재시도 루프를 타기 위해 임의의 RequestException을 발생시킵니다.
#                 raise requests.exceptions.RequestException("Hugging Face model is currently loading")
#         except Exception as e:
#             if not isinstance(e, requests.exceptions.RequestException):
#                 pass
#             else:
#                 raise
                
#     response.raise_for_status()


# def encode_batch(texts: list[str], batch_size: int = 16) -> list[list[float]]:
#     headers = _get_headers()
#     max_attempts = 5
    
#     for attempt in range(max_attempts):
#         # 1차 시도: 일반 도메인 호출
#         try:
#             response = requests.post(
#                 API_URL,
#                 headers=headers,
#                 json={"inputs": texts},
#                 timeout=30
#             )
#             return _parse_response(response, attempt, max_attempts)
#         except requests.exceptions.ConnectionError as e:
#             # DNS 해석 오류(NameResolutionError) 발생 시 DNS-over-HTTPS(DoH) 우회 동작 수행
#             if "NameResolutionError" in str(e) or "Failed to resolve" in str(e):
#                 print(f"[Embedder] DNS resolution failed. Attempting DNS-over-HTTPS bypass...")
#                 ip = _resolve_dns_over_https("api-inference.huggingface.co")
#                 if ip:
#                     print(f"[Embedder] Successfully resolved to IP: {ip}. Sending request directly...")
#                     try:
#                         # IP로 직접 호출하되, Host 헤더를 설정하여 TLS 가상 호스트를 맞춥니다.
#                         # SSL 인증서는 IP 주소와 일치하지 않으므로 verify=False로 우회합니다.
#                         ip_url = f"https://{ip}/models/BAAI/bge-m3"
#                         ip_headers = headers.copy()
#                         ip_headers["Host"] = "api-inference.huggingface.co"
                        
#                         response = requests.post(
#                             ip_url,
#                             headers=ip_headers,
#                             json={"inputs": texts},
#                             timeout=30,
#                             verify=False
#                         )
#                         return _parse_response(response, attempt, max_attempts)
#                     except Exception as ip_err:
#                         print(f"[Embedder] Direct IP request failed: {ip_err}")
            
#             if attempt == max_attempts - 1:
#                 raise RuntimeError(f"Failed to fetch embeddings from Hugging Face: {e}") from e
#             time.sleep(2)
#         except requests.exceptions.RequestException as e:
#             if attempt == max_attempts - 1:
#                 raise RuntimeError(f"Failed to fetch embeddings from Hugging Face: {e}") from e
#             time.sleep(2)
            
#     raise RuntimeError("Failed to get embeddings from Hugging Face Inference API after retries.")


"""BGE-M3 임베딩 래퍼 — sentence-transformers 로컬 실행 버전.

외부 API(HuggingFace Inference API) 의존을 제거하고 서버 내에서 직접 모델을 실행합니다.
모델은 최초 실행 시 HuggingFace Hub에서 다운로드되어 캐시됩니다.
"""
from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "BAAI/bge-m3"


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
