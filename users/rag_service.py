"""RAG 코디 추천 서비스 — Gemini(의도+앵커 추출 / 생성) + BGE-M3 + Qdrant.

embedder/retriever/prompts는 RAG에서 ailook_api로 vendored됨 (users/rag_core/).
→ 앱 실행에 RAG 레포가 필요 없음. RAG는 오프라인 코퍼스 파이프라인 전용.
generation은 로컬 Qwen 대신 Gemini로 통일 (design.md D5).
"""
from __future__ import annotations

import json
import time
from functools import lru_cache

from django.conf import settings

# RAG 런타임 코어 (vendored)
from .rag_core import embedder, prompts, retriever

from .models import Item, UserProfile

GEMINI_MODEL = "gemini-2.5-flash"
TOP_K = 5
# 코퍼스 outfit 이미지 서빙 prefix (urls.py의 rag-images 라우트와 일치)
IMAGE_URL_PREFIX = "/rag-images"

_PERSONA = (
    "당신은 친절하고 전문적이며 센스 있는 패션 코디네이터 AI인 'AI Closet Stylist'입니다. "
    "한국 20대 데일리 캐주얼에 특화되어 있습니다."
)


# ---------------------------------------------------------------- clients

@lru_cache(maxsize=1)
def _genai_client():
    from google import genai
    return genai.Client(api_key=settings.GEMINI_API_KEY)


@lru_cache(maxsize=1)
def _qdrant():
    from qdrant_client import QdrantClient
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


def warm_up() -> None:
    """BGE-M3 모델을 미리 로드 (startup 선로드, design.md D6)."""
    embedder.encode("워밍업")


_TRANSIENT = ("503", "unavailable", "429", "resource_exhausted", "overloaded",
              "high demand")


def _gen(contents: str, config: dict | None = None, retries: int = 3):
    """Gemini 생성 + transient(503/429/overload) 재시도 backoff."""
    last_err = None
    for attempt in range(retries):
        try:
            return _genai_client().models.generate_content(
                model=GEMINI_MODEL, contents=contents, config=config)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if attempt < retries - 1 and any(t in msg for t in _TRANSIENT):
                time.sleep(1.5 * (attempt + 1))
                last_err = e
                continue
            raise
    raise last_err  # pragma: no cover


# ---------------------------------------------------------------- helpers

_GENDER_MAP = {
    "남": "man", "남성": "man", "남자": "man", "man": "man", "male": "man",
    "여": "woman", "여성": "woman", "여자": "woman", "woman": "woman", "female": "woman",
}


def map_gender(raw: str | None) -> str:
    """프로필/추출 성별 → 코퍼스 gender(woman|man|any)."""
    if not raw:
        return "any"
    return _GENDER_MAP.get(str(raw).strip().lower(), "any")


def _profile_context(profile_data: dict | None) -> str:
    if not profile_data:
        return ""
    parts = []
    if profile_data.get("gender"):
        parts.append("성별: " + str(profile_data["gender"]))
    if profile_data.get("age"):
        parts.append("연령대: " + str(profile_data["age"]))
    if profile_data.get("height"):
        parts.append("키: " + str(profile_data["height"]) + "cm")
    if profile_data.get("weight"):
        parts.append("몸무게: " + str(profile_data["weight"]) + "kg")
    if profile_data.get("nickname"):
        parts.append("닉네임: " + str(profile_data["nickname"]))
    if not parts:
        return ""
    return "사용자 프로필 정보:\n" + "\n".join(parts) + "\n\n"


def resolve_profile_data(user, profile_data: dict | None) -> dict | None:
    """요청 바디 profile 우선, 없으면 DB UserProfile."""
    if profile_data:
        return profile_data
    try:
        p = user.profile
        return {
            "gender": p.gender, "age": p.age, "height": p.height,
            "weight": p.weight, "nickname": p.nickname,
        }
    except UserProfile.DoesNotExist:
        return None


def _history_text(session, limit: int = 6) -> str:
    """최근 대화 이력 텍스트 (현재 막 저장된 user 메시지 제외)."""
    msgs = list(session.messages.order_by("created_at"))[:-1]
    msgs = msgs[-limit:]
    out = []
    for m in msgs:
        label = "사용자" if m.role == "user" else "AI"
        out.append(f"{label}: {m.text}")
    return "\n".join(out)


# ---------------------------------------------------------------- anchor (D10)

# Item.category → AnchorItem.category. shoes/accessory는 앵커 불가.
_CATEGORY_MAP = {"top": "tops", "bottom": "bottom"}


def anchor_from_item(item: Item) -> tuple[dict | None, bool]:
    """클로젯 Item → AnchorItem dict. (anchor, ok). ok=False면 앵커 불가 카테고리."""
    category = _CATEGORY_MAP.get(item.category)
    if not category:
        return None, False
    details_parts = []
    if item.description:
        details_parts.append(item.description)
    if item.tags:
        details_parts.append(" ".join(str(t) for t in item.tags))
    return {
        "category": category,
        "type": item.kind or item.name,
        "color": None, "fit": None, "pattern": None,
        "material": None, "length": None,
        "details": " ".join(details_parts) or None,
    }, True


# ---------------------------------------------------------------- Gemini calls

_EXTRACT_INSTRUCTION = """\
사용자 메시지가 (1) 코디 추천 요청인지 (2) 일반 잡담/질문인지 판별하고, 추천이면 앵커 아이템 정보를 추출하세요.

반드시 아래 JSON 스키마로만 응답:
{
  "intent": "recommend" | "chat",
  "reply": string | null,        // intent=chat일 때만, 한국어 답변 (스타일리스트 톤)
  "anchor": {                    // intent=recommend일 때만
    "category": "tops" | "bottom" | "one_piece",
    "type": string,              // 예: "hoodie", "jeans"
    "color": string | null,
    "fit": "slim"|"regular"|"loose"|"oversized" | null,
    "pattern": string | null,
    "material": string | null,
    "length": string | null,
    "details": string | null
  } | null,
  "gender": "woman" | "man" | "unisex" | "any",
  "substyle": "street"|"minimal"|"city"|"y2k"|"athleisure" | null,
  "style_hint": string | null    // 자유 표현 (예: "오버사이즈 느낌으로")
}
앵커 정보가 부족해도 추천 요청이면 intent=recommend, 알 수 있는 필드만 채우고 나머지는 null."""


def classify_and_extract(message: str, history_text: str) -> dict:
    """Gemini 1콜: 의도 판별 + 앵커 추출 (design.md D3)."""
    prompt = (
        f"{_PERSONA}\n\n{_EXTRACT_INSTRUCTION}\n\n"
        + (f"[이전 대화]\n{history_text}\n\n" if history_text else "")
        + f"[사용자 메시지]\n{message}"
    )
    try:
        resp = _gen(prompt, config={
            "response_mime_type": "application/json", "temperature": 0.2,
            "thinking_config": {"thinking_budget": 0}})
        data = json.loads(resp.text)
    except Exception:
        # 파싱 실패 시 잡담으로 폴백
        return {"intent": "chat", "reply": None, "anchor": None,
                "gender": "any", "substyle": None, "style_hint": None}
    data.setdefault("intent", "chat")
    data.setdefault("gender", "any")
    data.setdefault("substyle", None)
    data.setdefault("style_hint", None)
    return data


def _plain_chat(message: str, profile_context: str, history_text: str) -> str:
    """잡담/일반 응답 (Gemini)."""
    prompt = (
        f"{_PERSONA} 사용자의 신체 특성과 스타일에 맞춰 한국어로 다정하고 구체적으로 답하세요.\n\n"
        + profile_context
        + (f"이전 대화:\n{history_text}\n\n" if history_text else "")
        + "사용자: " + message
    )
    resp = _gen(prompt, config={"thinking_config": {"thinking_budget": 0}})
    return resp.text


# ---------------------------------------------------------------- outfit URL

def _image_url(metadata: dict, request) -> str:
    gender = metadata.get("gender", "")
    filename = metadata.get("image", "")
    path = f"{IMAGE_URL_PREFIX}/{gender}/{filename}"
    return request.build_absolute_uri(path) if request else path


def _outfit_dict(r, request) -> dict:
    caption = r.metadata.get("caption") or ""
    return {
        "image": r.image,
        "image_url": _image_url(r.metadata, request),
        "score": round(r.score, 4),
        "substyle": r.metadata.get("substyle"),
        "caption_snippet": caption[:120],
    }


# ---------------------------------------------------------------- recommend

def recommend(anchor: dict, style_hint: str | None, gender: str,
              substyle: str | None, profile_context: str,
              history_text: str, request) -> dict:
    """앵커 → BGE-M3 임베딩 → Qdrant 검색 → Gemini 생성 → {reply, outfits}."""
    anchor_text = prompts.build_anchor_text(anchor)
    query_text = f"{anchor_text} {style_hint or ''}".strip()
    query_vec = embedder.encode(query_text)

    results = retriever.retrieve(
        client=_qdrant(),
        collection=settings.QDRANT_COLLECTION,
        query_vector=query_vec,
        gender=gender,
        substyle=substyle,
        top_k=TOP_K,
    )

    # confidence 로그 — 서빙 시 각 후보의 점수 출력 (유지)
    score_str = ", ".join(f"{r.image}:{r.score:.4f}" for r in results) or "none"
    print(f"[RAG] query={query_text!r} gender={gender} substyle={substyle} "
          f"→ {len(results)} hits [{score_str}]")

    if not results:
        return {"reply": "조건에 맞는 코디를 찾지 못했어요. 다른 아이템이나 스타일로 다시 시도해 주세요.",
                "outfits": []}

    # 후보 전체를 생성에 넘기고 LLM이 어울리는 것을 선별 (그 질문 이전 동작으로 복원)
    prompt_text = prompts.build_generation_prompt(
        anchor_item=anchor,
        style_hint=style_hint,
        gender=gender,
        substyle=substyle,
        outfits=[r.metadata for r in results],
    )
    if profile_context or history_text:
        prefix = profile_context
        if history_text:
            prefix += f"[이전 대화]\n{history_text}\n\n"
        prompt_text = prefix + prompt_text

    resp = _gen(prompt_text, config={"thinking_config": {"thinking_budget": 0}})
    return {
        "reply": resp.text,
        "outfits": [_outfit_dict(r, request) for r in results],
    }


# ---------------------------------------------------------------- orchestrator

def handle(request, session, user_message: str, anchor_item_id=None,
           profile_data: dict | None = None) -> dict:
    """챗 1턴 처리. {reply, outfits} 반환. (user 메시지는 view에서 이미 저장됨)"""
    if not settings.GEMINI_API_KEY:
        return {"reply": "API 키가 설정되지 않았습니다.", "outfits": []}

    profile_data = resolve_profile_data(request.user, profile_data)
    profile_context = _profile_context(profile_data)
    history_text = _history_text(session)

    try:
        # 경로 1: 클로젯 아이템 탭 → 구조화 앵커 (강제 recommend)
        if anchor_item_id:
            try:
                item = Item.objects.get(id=anchor_item_id, user=request.user)
            except Item.DoesNotExist:
                return {"reply": "선택한 아이템을 찾을 수 없어요.", "outfits": []}
            anchor, ok = anchor_from_item(item)
            if not ok:
                return {"reply": "신발·액세서리는 아직 코디 기준 아이템으로 쓸 수 없어요. 상의나 하의를 골라주세요.",
                        "outfits": []}
            gender = map_gender(profile_data.get("gender") if profile_data else None)
            res = recommend(anchor, user_message or None, gender, None,
                            profile_context, history_text, request)
            # create-cody 슬롯 연결용 — 앵커는 사용자의 실제 Item (D9)
            res["anchor_item_id"] = item.id
            res["anchor_category"] = item.category  # 'top' | 'bottom'
            return res

        # 경로 2: 자유 텍스트 → 의도+앵커 추출
        extracted = classify_and_extract(user_message, history_text)
        if extracted.get("intent") == "recommend" and extracted.get("anchor"):
            gender = extracted.get("gender") or "any"
            if gender == "any":
                gender = map_gender(profile_data.get("gender") if profile_data else None)
            return recommend(
                extracted["anchor"], extracted.get("style_hint"), gender,
                extracted.get("substyle"), profile_context, history_text, request,
            )

        # 잡담
        reply = extracted.get("reply") or _plain_chat(user_message, profile_context, history_text)
        return {"reply": reply, "outfits": []}
    except Exception as e:
        return {"reply": "AI 처리 중 오류가 발생했습니다: " + str(e), "outfits": []}
