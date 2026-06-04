"""Generation prompt 조립."""
from __future__ import annotations

import json


def build_anchor_text(anchor_item: dict) -> str:
    """앵커 아이템 dict → embedding 입력 텍스트. 순서: fit color type material details."""
    fields = ["fit", "color", "type", "material", "details"]
    parts = [str(anchor_item[f]) for f in fields if anchor_item.get(f)]
    return " ".join(parts)


def build_generation_prompt(
    anchor_item: dict,
    style_hint: str | None,
    gender: str,
    substyle: str | None,
    outfits: list[dict],
) -> str:
    anchor_category = anchor_item.get("category", "")
    anchor_fields = "\n".join(
        f"  {k}: {v}"
        for k, v in anchor_item.items()
        if k != "category" and v is not None
    )

    outfits_text = "\n".join(
        f"{i + 1}. {json.dumps(o, ensure_ascii=False)}"
        for i, o in enumerate(outfits)
    )

    return f"""당신은 한국 20대 데일리 캐주얼에 특화된 AI 스타일링 어드바이저입니다.
아래 검색된 outfit {len(outfits)}개를 제시된 순서 그대로(추천 적합도 높은 순) 빠짐없이 추천 설명하세요.
임의로 일부만 고르거나 순서를 바꾸지 말고, 제시된 모든 outfit을 각각 한 번씩 다루세요.

[사용자 보유 아이템] (앵커)
카테고리: {anchor_category}
{anchor_fields}
※ 위 아이템은 사용자가 이미 보유한 것입니다.

[스타일 힌트]
{style_hint or "없음"}

[선택 필터]
성별: {gender}
서브스타일: {substyle or "전체"}

[검색된 outfits]
{outfits_text}

[응답 작성 규칙]
- 자연스러운 한국어 (존대), 패션 용어 활용
- 각 outfit 설명은 반드시 그 outfit의 정확한 [image: 파일명.jpg] 토큰으로 시작하세요 — 예: [image: man_casual_outfit_59.jpg]
- 토큰 없이 outfit을 언급하거나 설명하지 말 것. 제시된 모든 outfit을 빠짐없이 각각 [image:] 토큰과 함께 인용
- "이미지", "사진" 등 다른 표현으로 파일명을 언급하지 말 것. 반드시 [image: ...] 토큰 사용
- 각 outfit마다: 앵커 아이템({anchor_category})과 어울리는 이유, 앵커 외 핵심 아이템의 색·fit·소재 조합 포인트, 전체 실루엣과 스타일 무드
- 마지막에 styling tip 한 줄
- 답변 길이 약 300-500자
- 검색 결과에 없는 아이템·브랜드는 절대 추천하지 마세요
- 출력은 plain text. 마크다운 헤더/리스트 사용 안 함"""
