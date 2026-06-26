# ADR: NetBox 장비 상세 노출 + 후보 부가정보 항목 관리

- **Status:** Accepted
- **Date:** 2026-06-26
- **Builds on:** `2026-06-20-candidate-pool.md`, `2026-06-19-spec-cost-separation.md`

## Context

후보풀에서 "원본(NetBox) 사양은 다 보고 싶고, 가격처럼 원본에 없는 우리 부가정보는 따로
입력·구분해서 보고 싶다. 그리고 어떤 부가정보 항목을 쓸지는 기준정보에서 관리하고 싶다"는 요구.

NetBox `devicetype-library`의 전체 스펙(물리·전원·인터페이스·모듈베이·데이터시트 등)은 이미
카탈로그 인덱스(`specs.data` JSON)에 들어 있었지만 **어떤 API도 노출하지 않았고**, 후보풀은
이름·카테고리·가격만 보여줬다.

## Decision

### 1. 원본(read-only) vs 부가정보(우리, editable) 분리 — 기존 원칙 강화
- **원본 = NetBox catalog**(`vendor/devicetype-library`, 읽기 전용). **부가정보 = 우리 오버레이**
  (`pricing/` 가격 + `meta/` 커스텀 필드). 카탈로그는 절대 손대지 않는다(Tier-0).
- 후보풀 UI에서 이 둘을 **시각적으로 분리**: 부가정보(단가·비고·메타)는 accent 밴드로 강조해
  편집 가능 영역으로, 원본 사양은 `▸ 원본 사양(NetBox)` 펼침(읽기 전용, "NetBox 원본" 태그).

### 2. `GET /api/catalog/device/{slug}` — 전체 스펙 + 요약
하나의 엔드포인트가 두 용도를 모두 커버:
- `components`: interfaces/power-ports(maximum_draw·allocated_draw)/console-ports/module-bays/
  device-bays/front·rear-ports/power-outlets 전체 — **후보풀 전체 상세 + 후보추가 팝업**용.
- `summary`: `max_power_w`(power-ports 합), `port_summary`(타입별 개수), 컴포넌트 카운트 +
  물리(U/풀뎁스/무게/공조)/`datasheets`(comments의 마크다운 링크 파싱) — **/place·/placed 요약**용.
- 화면 분담: 후보풀/후보추가=전체, 배치/태그=요약(가벼운 뷰).

### 3. 후보 부가정보 항목 관리 — 기준정보
- `meta/fields.yaml`의 `applies_to: candidate` 필드 정의를 **기준정보 화면에서 CRUD**.
  `GET/POST /api/meta/fields`, `DELETE /api/meta/fields/{key}` + `overlay.meta.save_fields`
  (전체 applies_to 라운드트립). 쓰기 후 `ws.fields` 재로딩 → `/api/candidate-fields` 즉시 반영
  (가격 라이브 리프레시와 동일 패턴). 타입 string/int/enum/bool/date, enum은 options.
- 후보풀의 부가정보 입력칸은 이 정의를 그대로 따른다(타입별 입력 + required→amber).

## Consequences
- 정적 데모: device-detail을 후보풀+배치 장비+device 검색 코퍼스(최대 500)만큼 캡처(쓰기 차단은
  그대로). `_api.js` 크기 증가하나 데모 한정.
- 부가정보는 **후보풀에 담긴 장비에만** 존재(원본 카탈로그 전체가 아니라 큐레이션된 후보에만 우리
  데이터가 붙는다)는 기존 candidate-pool 모델과 정확히 일치.
