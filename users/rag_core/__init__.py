"""RAG 런타임 코어 (RAG/src에서 vendored — embedder/retriever/prompts).

ailook_api를 self-contained로 만들기 위해 RAG 레포에서 복사함.
RAG 레포는 오프라인 코퍼스 파이프라인(captioning/indexing/eval) 전용으로만 남음.
임베딩 모델 등 변경 시 이 사본도 동기화 필요.
"""
