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
    anchor_type = anchor_item.get("type") or "(미지정)"
    anchor_color = anchor_item.get("color") or "(미지정)"
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
사용자가 보유한 기준 아이템(앵커)을 '실제로 포함한' 코디 예시를 골라, 그 코디에서 앵커 외의
아이템들이 앵커와 어떻게 어울리는지 설명하는 것이 임무입니다.

[가장 중요한 원칙]
- 추천하는 이미지에는 앵커와 같은 종류({anchor_type})의 옷이 캡션상 '실제로' 들어 있어야 합니다.
- 이미지에 없는 옷을 있는 것처럼 지어내지 마세요. 특히 "당신의 {anchor_type}을 매치하면/넣으면"
  같은 가정·합성 표현은 절대 금지. 이미지에 실재하는 옷만 묘사합니다.

[사용자 보유 아이템] (앵커)
카테고리: {anchor_category}
종류(type): {anchor_type}
색(color): {anchor_color}
{anchor_fields}

[스타일 힌트] {style_hint or "없음"}
[선택 필터] 성별: {gender} / 서브스타일: {substyle or "전체"}

[검색된 후보 outfits]
{outfits_text}

[판정 절차 — 반드시 순서대로]
1) 각 후보의 caption을 읽고, 앵커와 같은 종류({anchor_type})의 옷이 그 코디에 실제로 포함됐는지 판정.
2) 포함된 후보만 추천. 포함 안 된 후보는 언급도 설명도 하지 말 것(이미지 토큰도 내지 말 것).
3) [tier: 종류 없음] 포함된 후보가 하나도 없으면 — 추천을 지어내지 말고 이렇게 정직하게:
   "요청하신 '{anchor_type}' 코디를 데이터에서 찾지 못했어요. 비슷한 무드의 코디는 다음과 같아요:"
   라고 안내한 뒤, 가장 가까운 후보 1개만 "이 코디는 {anchor_type}을 직접 포함하진 않지만 참고용"
   임을 분명히 밝히며 [image:] 토큰과 함께 제시.
4) [tier: 색 불일치] 포함된 후보 중 앵커 색({anchor_color})과 다른 색이면, 그 추천을 제시하기 전에 먼저:
   "요청하신 {anchor_color} {anchor_type}은 데이터에 없어요. 색은 다르지만 같은 {anchor_type} 코디예요:"
   라고 인정한 뒤 제시. (색이 일치하거나 앵커 색이 미지정이면 이 안내 생략)
5) [tier: 정확 일치] 종류·색 모두 맞으면 바로 추천 설명.

[각 추천 작성 규칙]
- 반드시 그 outfit의 정확한 [image: 파일명.jpg] 토큰으로 시작 — 예: [image: man_casual_outfit_141.jpg]
- "이미지", "사진" 등 다른 표현으로 파일명을 대신하지 말 것. 반드시 [image: ...] 토큰 사용.
- 이미지에 실재하는 옷만 묘사하되, 설명의 '초점'은 앵커({anchor_type}) 외의 아이템들
  (하의·신발·아우터·액세서리)이 앵커와 어떻게 어울리는가 — 색·핏·소재 조합과 전체 실루엣·무드.
- 자연스러운 한국어(존대), 패션 용어 활용. 각 추천 약 200-400자.
- 검색 결과(캡션)에 없는 아이템·브랜드는 절대 추천하지 마세요.
- 출력은 plain text. 마크다운 헤더/리스트 사용 안 함."""
