from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

from fastapi import APIRouter
from pydantic import BaseModel, Field, validator


CampaignMode = Literal["ON", "OFF"]


@dataclass
class Product:
    """
    내부 도메인 모델.

    - compatibility_tags: 메인 기기와 1개 이상 겹치는 태그가 없으면 추천 후보에서 제외.
    - stock: 현재 재고 수량.
    - eta_hours: 재고 0일 때, 다음 입고까지 남은 시간(시간 단위). 24시간 초과 시 후보에서 제외.
    - margin_score: 마진/재고령 관점의 점수(0~1 범위 가정).
    - inventory_age_days: 입고 후 경과 일수.
    - seller_convenience_score: 판매 편의성 점수(0~1 범위 가정).
    """

    product_id: str
    name: str
    price: float
    compatibility_tags: Sequence[str]
    stock: int
    eta_hours: Optional[float]
    margin_score: float
    inventory_age_days: int
    seller_convenience_score: float


class ProductInput(BaseModel):
    product_id: str = Field(..., description="제품 ID")
    name: str = Field(..., description="제품명")
    price: float = Field(..., ge=0, description="판매 가격 (USD)")
    compatibility_tags: List[str] = Field(
        default_factory=list,
        description="호환성 태그 목록. 메인 기기와 1개 이상 겹치지 않으면 제외.",
    )
    stock: int = Field(..., ge=0, description="현재 재고 수량")
    eta_hours: Optional[float] = Field(
        default=None,
        description="재고가 0일 때 다음 입고까지 남은 시간(시간 단위). 24시간 초과 시 제외.",
    )
    margin_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="마진/재고 측면 점수(0~1). 높을수록 좋음.",
    )
    inventory_age_days: int = Field(
        ...,
        ge=0,
        description="해당 로트의 재고령(일). 90일 이상일 경우 Investor 가중 보정.",
    )
    seller_convenience_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="판매 편의성 점수(0~1). 번들 구성, 설명 난이도 등을 반영.",
    )

    @validator("compatibility_tags", pre=True)
    def _normalize_tags(cls, v):
        if v is None:
            return []
        return [str(t).strip() for t in v if str(t).strip()]

    def to_domain(self) -> Product:
        return Product(
            product_id=self.product_id,
            name=self.name,
            price=float(self.price),
            compatibility_tags=self.compatibility_tags,
            stock=int(self.stock),
            eta_hours=float(self.eta_hours) if self.eta_hours is not None else None,
            margin_score=float(self.margin_score),
            inventory_age_days=int(self.inventory_age_days),
            seller_convenience_score=float(self.seller_convenience_score),
        )


class StrategicRecommendation(BaseModel):
    product_id: str
    name: str
    total_score: float = Field(..., description="최종 가중치 기반 점수")
    ceo_score: float = Field(..., description="브랜드/프리미엄 관점 점수")
    investor_score: float = Field(..., description="마진·재고령 관점 점수 (보정 후)")
    seller_score: float = Field(..., description="판매 편의 관점 점수")
    campaign_mode: CampaignMode
    reason: str = Field(
        ...,
        description='판매자용 자연어 설명. "이 제품은 [이유]로 인해 현재 가장 적합한 추천입니다" 형식.',
    )


class RecommendationRequest(BaseModel):
    main_device: ProductInput = Field(..., description="메인 기기 정보")
    candidates: List[ProductInput] = Field(
        default_factory=list, description="추천 후보 상품 목록"
    )
    campaign_mode: CampaignMode = Field(
        default="OFF", description="동적 캠페인 모드 (ON/OFF)"
    )


class RecommendationResponse(BaseModel):
    main_device_id: str
    campaign_mode: CampaignMode
    recommendations: List[StrategicRecommendation]


class StrategicAssociationOrchestrator:
    """
    애플 리테일 '전략적 연관분석 오케스트레이터' 핵심 구현.

    - 데이터 유효성 검사
    - 가중치 기반 스코어링(CEO / Investor / Seller)
    - 동적 캠페인 모드
    - 자연어 설명 생성
    - 장애 대응(Fail-safe)
    """

    # 기본 가중치
    BASE_W_CEO = 0.3
    BASE_W_INVESTOR = 0.4
    BASE_W_SELLER = 0.3

    # 프리미엄 기준 가격(USD)
    PREMIUM_PRICE_THRESHOLD = 1000.0

    # 재고령 임계값(일)
    AGED_INVENTORY_DAYS = 90

    # Fail-safe Best-Seller 3종 (간단한 예시용 상수)
    BEST_SELLER_FALLBACK: List[StrategicRecommendation] = [
        StrategicRecommendation(
            product_id="BS-001",
            name="AppleCare+ for iPhone",
            total_score=0.95,
            ceo_score=0.9,
            investor_score=0.9,
            seller_score=0.95,
            campaign_mode="OFF",
            reason="이 제품은 전 제품군에 안정적인 부가가치를 제공하여 현재 가장 적합한 추천입니다",
        ),
        StrategicRecommendation(
            product_id="BS-002",
            name="USB‑C 전원 어댑터",
            total_score=0.9,
            ceo_score=0.85,
            investor_score=0.88,
            seller_score=0.9,
            campaign_mode="OFF",
            reason="이 제품은 대부분의 기기와 호환되며 구매 전환율이 높아 현재 가장 적합한 추천입니다",
        ),
        StrategicRecommendation(
            product_id="BS-003",
            name="MagSafe 듀얼 충전기",
            total_score=0.88,
            ceo_score=0.9,
            investor_score=0.82,
            seller_score=0.88,
            campaign_mode="OFF",
            reason="이 제품은 프리미엄 액세서리로 번들 구성 시 객단가를 높일 수 있어 현재 가장 적합한 추천입니다",
        ),
    ]

    def _compute_weights(self, campaign_mode: CampaignMode):
        """
        동적 캠페인 모드에 따른 가중치 설정.

        - 기본: CEO 0.3, Investor 0.4, Seller 0.3
        - 캠페인 모드 ON: CEO 0.6, Investor/Seller는 기존 비율(4:3)을 유지하는 선에서 재조정.
          → Investor 0.24, Seller 0.16
        """
        if campaign_mode == "ON":
            w_ceo = 0.6
            rest = 1.0 - w_ceo
            base_rest = self.BASE_W_INVESTOR + self.BASE_W_SELLER
            if base_rest <= 0:
                return self.BASE_W_CEO, self.BASE_W_INVESTOR, self.BASE_W_SELLER
            ratio_inv = self.BASE_W_INVESTOR / base_rest
            ratio_seller = self.BASE_W_SELLER / base_rest
            w_inv = rest * ratio_inv
            w_seller = rest * ratio_seller
            return w_ceo, w_inv, w_seller
        return self.BASE_W_CEO, self.BASE_W_INVESTOR, self.BASE_W_SELLER

    @staticmethod
    def _is_compatible(main: Product, candidate: Product) -> bool:
        if not main.compatibility_tags or not candidate.compatibility_tags:
            return False
        main_tags = {t.lower() for t in main.compatibility_tags}
        cand_tags = {t.lower() for t in candidate.compatibility_tags}
        return len(main_tags & cand_tags) > 0

    @staticmethod
    def _is_stock_valid(candidate: Product) -> bool:
        if candidate.stock > 0:
            return True
        if candidate.stock == 0 and candidate.eta_hours is not None:
            return candidate.eta_hours <= 24.0
        return False

    def _ceo_score(self, main: Product, candidate: Product) -> float:
        """
        CEO 관점 점수.

        - 기본: 가격 수준이 높을수록(브랜드 일관성 측면) 점수↑.
        - 메인 기기가 프리미엄(>= 1000달러)인 경우, 너무 저가인 액세서리는 감점.
        """
        # 가격을 메인 기기 가격 대비 0~1 범위로 정규화
        if main.price <= 0:
            base = 0.5
        else:
            base = min(candidate.price / main.price, 1.2)
        base_norm = max(0.1, min(base, 1.0))

        if main.price >= self.PREMIUM_PRICE_THRESHOLD:
            # 프리미엄 기기: 메인 가격의 20% 미만이면 감점
            ratio = candidate.price / main.price if main.price > 0 else 0
            if ratio < 0.2:
                base_norm *= 0.6  # 저가 상품 감점
            elif ratio < 0.4:
                base_norm *= 0.8
        return round(float(base_norm), 4)

    def _investor_score(self, candidate: Product) -> float:
        """
        Investor 관점 점수.

        - 기본: margin_score 사용.
        - 재고령이 90일 이상이면 가중 점수 1.5배 (재고 턴오버 개선 목적).
        """
        base = max(0.0, min(candidate.margin_score, 1.0))
        if candidate.inventory_age_days >= self.AGED_INVENTORY_DAYS:
            base *= 1.5
        return round(float(min(base, 1.5)), 4)

    @staticmethod
    def _seller_score(candidate: Product) -> float:
        """
        Seller 관점 점수.

        - seller_convenience_score 그대로 사용(0~1).
        """
        base = max(0.0, min(candidate.seller_convenience_score, 1.0))
        return round(float(base), 4)

    def _build_reason(
        self,
        main: Product,
        candidate: Product,
        ceo_score: float,
        investor_score: float,
        seller_score: float,
        campaign_mode: CampaignMode,
    ) -> str:
        reasons: List[str] = []

        if self._is_compatible(main, candidate):
            reasons.append("메인 기기와 호환성이 높아 번들 제안에 자연스럽습니다")

        if main.price >= self.PREMIUM_PRICE_THRESHOLD and ceo_score >= 0.8:
            reasons.append("프리미엄 메인 기기와 가격·브랜드 톤이 잘 맞습니다")
        elif ceo_score >= 0.7:
            reasons.append("가격대와 브랜드 포지션이 메인 기기와 균형을 이룹니다")

        if investor_score > 1.0:
            reasons.append("재고령이 길어 마진과 재고 턴오버 개선에 유리합니다")
        elif investor_score >= 0.8:
            reasons.append("마진과 재고 상태가 양호해 점포 수익성에 기여합니다")

        if seller_score >= 0.8:
            reasons.append("설명이 간단하고 교차 판매 제안이 쉬워 판매자 입장에서 다루기 편합니다")

        if campaign_mode == "ON":
            reasons.append("현재 캠페인 모드에서 객단가 상승에 기여하도록 설계되었습니다")

        if not reasons:
            reasons.append("가격·마진·판매 편의성이 고르게 균형을 이루고 있습니다")

        core = " 그리고 ".join(reasons[:2]) if len(reasons) >= 2 else reasons[0]
        return f"이 제품은 {core}로 인해 현재 가장 적합한 추천입니다"

    def recommend(
        self, main_device: Product, candidates: Sequence[Product], campaign_mode: CampaignMode = "OFF"
    ) -> List[StrategicRecommendation]:
        """
        전략적 연관분석 추천 실행.

        - 입력: 메인 기기 1개, 후보 상품 목록
        - 출력: 스코어링 및 자연어 설명이 포함된 정렬된 추천 리스트
        """
        try:
            w_ceo, w_inv, w_seller = self._compute_weights(campaign_mode)
            results: List[StrategicRecommendation] = []

            for cand in candidates:
                # 1. 데이터 유효성 검사
                if not self._is_compatible(main_device, cand):
                    continue
                if not self._is_stock_valid(cand):
                    continue

                # 2. 스코어링
                ceo = self._ceo_score(main_device, cand)
                investor = self._investor_score(cand)
                seller = self._seller_score(cand)

                total = w_ceo * ceo + w_inv * investor + w_seller * seller
                total = float(round(total, 4))

                reason = self._build_reason(
                    main=main_device,
                    candidate=cand,
                    ceo_score=ceo,
                    investor_score=investor,
                    seller_score=seller,
                    campaign_mode=campaign_mode,
                )

                results.append(
                    StrategicRecommendation(
                        product_id=cand.product_id,
                        name=cand.name,
                        total_score=total,
                        ceo_score=ceo,
                        investor_score=investor,
                        seller_score=seller,
                        campaign_mode=campaign_mode,
                        reason=reason,
                    )
                )

            # 점수 순 정렬
            results.sort(key=lambda r: r.total_score, reverse=True)
            return results or self.BEST_SELLER_FALLBACK

        except Exception:
            # 5. 장애 대응(Fail-safe): 사전 정의된 Best-Seller 3종 반환
            return self.BEST_SELLER_FALLBACK


# FastAPI 연동용 라우터
router = APIRouter(prefix="/api", tags=["strategic-association"])
_orchestrator = StrategicAssociationOrchestrator()


@router.post("/strategic-association-recommendations", response_model=RecommendationResponse)
def api_strategic_association_recommendations(payload: RecommendationRequest) -> RecommendationResponse:
    """
    전략적 연관분석 오케스트레이터 API 엔드포인트.

    - 입력: 메인 기기 + 후보 상품들 + 캠페인 모드(ON/OFF)
    - 출력: 가중치 기반 스코어 및 자연어 설명이 포함된 추천 리스트
    """
    main = payload.main_device.to_domain()
    candidates = [c.to_domain() for c in payload.candidates]
    recs = _orchestrator.recommend(main_device=main, candidates=candidates, campaign_mode=payload.campaign_mode)
    return RecommendationResponse(
        main_device_id=main.product_id,
        campaign_mode=payload.campaign_mode,
        recommendations=recs,
    )

