# 브리프: 설계 모델 + BOM 엔진 (릴리즈 인식, 원화 CAPEX)

**목표**
랙 설계를 비용으로 환산한다 — 조직계층/랙/배치 YAML과 원화 가격 오버레이를 읽어 기존 카탈로그
인덱스와 조인하고, CAPEX 집계(전체 + 릴리즈별 델타)와 전력 용량 집계를 산출한다. Python API와
`bombom bom` CLI로 제공.

## Scope IN (포함)
- **설계 스키마 + 로더**: `offerings/<o>/regions/<r>/zones/<z>/rack-groups/<g>/racks/<rack>.yaml`.
  랙 파일은 카탈로그 `rack_type`(manufacturer+slug)을 참조하고
  `placements[] = {device: <slug>, position: <U>, release: <태그>, qty?}` 와 선택적
  `custom_line_items[] = {name, qty, unit_cost, release?}` 를 가진다.
- **검증**(카탈로그 인덱스 대조): device/rack slug 존재, `position`+u_height가 랙 `u_height` 내,
  같은 랙 내 U 중복 없음. 위반 항목은 (경로+사유) 보고하고 집계 제외 — 조용히 버리지 않음.
- **가격 오버레이 로더** `pricing/<vendor>.yaml` — `PriceEntry: 키(manufacturer+slug | model |
  part_number) → {unit_cost: <정수 KRW>, currency: KRW, valid_from?, valid_to?, source?}`.
  `pricing/`에만 두고 카탈로그·설계 파일에는 절대 쓰지 않음.
- **BOM 엔진**: 임의 서브트리 순회 → 라인아이템 `(부품키, 수량)`으로 평탄화 (**수량 = 배치 인스턴스
  수** + custom line items) → 카탈로그 스펙 + 가격 조인(`valuation_date` 기준 시점가, 기본 오늘)
  → **원화 CAPEX 집계**: 전체, 랙별, 카테고리별, **릴리즈별** + **선택 릴리즈 델타**. 병행
  **전력 집계**(Σ max draw, W).
- **미가격 처리**: 가격 매칭 안 되는 항목은 `unpriced` 목록에 (수량과 함께) 표기·플래그 — 크래시
  금지, 조용한 ₩0 금지.
- **CLI + API**: `bombom bom <계층경로> [--release R26.07] [--as-of YYYY-MM-DD]` 출력;
  `from bombom.bom import compute_bom(...)` 가 구조화된 결과 반환.

## Scope OUT (제외)
- 웹 UI / FastAPI / REST / 랙 SVG 렌더링.
- OPEX / TCO / 전력의 비용 환산, 감가상각.
- 다중 통화 (원화 전용, 환율 환산 없음).
- git 커밋-온-라이트 (working tree YAML 읽기만; 설계 저장/커밋은 이후).
- 릴리즈를 실제 git 태그/브랜치와 결합 (지금은 placement의 텍스트 태그).
- 실제 전체 계층 데이터 작성 (테스트/데모용 소형 샘플 트리만).

## Constraints (제약)
- 파일: `bombom/catalog/**`, `vendor/devicetype-library/**` 읽기전용 유지 (`Catalog`/인덱스 재사용,
  카탈로그 패키지 수정 금지).
- 동작: 가격/분류 데이터는 카탈로그·설계 YAML에 **절대 기록하지 않음** (ADR spec-cost-separation).
  git이 원본, 인덱스는 재생성 캐시.
- 연동: 조인 키는 카탈로그 식별자와 정확히 일치 — device/rack은 `manufacturer+slug`, module은
  `model`(+part_number).

## Exit Criteria (완료 기준)
- [ ] 샘플 계층 + 가격 오버레이에서 `bombom bom offerings/cloud-a` 가 손계산 픽스처와 일치하는 총
  CAPEX(₩) 출력 (Σ 수량×단가).
- [ ] `bombom bom <경로> --release R26.07` 가 `release==R26.07` 배치만의 합 = 릴리즈 델타 출력;
  `--release` 변경 시 값이 결정적으로 변함.
- [ ] 존재하지 않는 device slug, U 범위 초과/중복 배치는 (파일경로+사유) 오류 보고되고 집계 제외
  (정상 항목은 계속 합산).
- [ ] 가격 없는 배치 장비는 `unpriced` 목록에 수량과 함께 표기되고 CLI에서 플래그 (조용한 ₩0 아님).
- [ ] `compute_bom()` 가 총 CAPEX, 랙별·카테고리별 분해, 릴리즈별 합계, 총 전력(W) 반환; `pytest`로
  (집계·검증·미가격) 커버 — 전부 통과.
- [ ] `valuation_date` 가 `valid_from/valid_to` 구간 가격을 선택; 한 키 가격 2건 픽스처에서 날짜에
  맞는 단가 반환.

## Risk Flags (위험)
- 조인 키 불일치 (device slug는 제조사 접두·전역 고유, module은 slug 없음) — 카탈로그 `Catalog`
  조회 재사용. 아니면 합계 누락.
- 시점가 모호성 (구간 겹침/개방형) — 규칙: `valid_from` ≤ 날짜 중 가장 최근 채택, 테스트.
- "배치 수량" vs placement `qty` 중복 계산 — 규칙: `qty`는 단일 배치 라인 배수(기본 1), 문서·테스트.
- 0U 장비(PDU)·`custom_line_items` 는 U 미점유여도 CAPEX 포함.
