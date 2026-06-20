# 2026-06-20 — 장비 후보풀(candidate pool) 모델: 별도 목록 + 가격 분리, 전역 범위

## Context
설계자는 NetBox 카탈로그(5,800+ device) 전체에서 바로 배치하지 않고, 먼저 **대상 후보 장비**를
선별하고 후보별로 **가격·부가정보**를 입력한 뒤, **그 후보풀에서만** 랙에 배치하길 원한다
(사용자 흐름, 2회 명시). 배치 결과는 가격 합산이 가능한 목록으로 본다.

## Decision
- **후보풀 = 별도 목록**(`candidates/pool.yaml`, 워크스페이스 **전역**)으로 둔다. 가격은 기존
  pricing 오버레이에 **분리** 저장한다(ADR spec-cost-separation 유지).
  - 매니페스트 행: `{slug, note?, added_at}`. slug = 카탈로그 device 슬러그(추가 시 카탈로그 존재
    검증). note = 자유 텍스트 부가정보.
  - **"가격 미정 후보"** 상태가 표현된다(후보풀엔 있으나 pricing 엔트리 없음) — 가격=후보와 분리한
    이유. (대안: "가격 엔트리 보유 = 후보"는 가격 미정 후보를 표현 못 함 → 기각.)
- **가격 입력**은 후보 화면에서 `pricing/manual.yaml`에 upsert(slug 키, unit_cost/source/
  valid_from). 기존 `PriceBook`이 `pricing/*.yaml`을 읽으므로 별도 reader 불필요.
- **범위 = 전역**(워크스페이스 공통). 지금 pricing 구조와 동일해 가장 단순하고 관리 지점이 하나다.
  (대안: 오퍼링별 후보풀 → clone 시나리오엔 맞지만 관리 지점 증가 + 배치 시 풀 선택 로직 필요 →
  기각, 필요해지면 후속.)
- **라이브 반영**: 가격 쓰기 직후 공유 `ws.pricebook`을 reload해 대시보드/리포트/confirm/후보
  화면이 서버 재시작 없이 새 가격을 즉시 본다.
- **git 비노출**: pool/pricing 쓰기·커밋은 백엔드. 화면은 도메인 언어만.

## Consequences
- 신규: `bombom/candidates.py`(pool CRUD + `set_price`), API `GET/POST /api/candidates`,
  `PUT/DELETE /api/candidates/{slug}`, `/candidates`(`web/candidates.html`).
- Phase 3에서 에디터 배치 검색을 **후보풀로 제한**한다(이번엔 카탈로그 전체 검색 유지).
- Phase 4에서 배치예정 장비 목록/합산은 confirm gate·dashboard·report와 같은 BOM 경로를 쓴다.
- 후보 제거는 허용(아직 배치 안 된 큐레이션). 단, 이미 **배치된** 장비는 append-only 대상이라
  별개다.

## Override conditions
오퍼링/리전별로 후보·가격이 갈리는 요구가 강해지면 범위를 오퍼링별로 확장하고 배치 시 적용 풀을
계층에서 해석한다. 가격 이력(시점별 단가) 관리가 커지면 `PriceEntry`의 valid_from/valid_to를
후보 화면에서 직접 다루도록 넓힌다(현재는 입력 시점 valid_from만 기록).
