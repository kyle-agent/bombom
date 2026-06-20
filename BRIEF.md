# Brief: 선정 → 배치 → 집계 흐름 (기준정보·Rack-Type 관리 / 장비 후보풀 / 배치 / 목록)

> Locked 2026-06-20. 사용자 흐름(2회 명시): 기준정보 관리(오퍼링·리전·AZ) → 메타정보
> 관리(Rack-Type) → 랙/장비 추가 → 장비 **후보 선택 화면**(가격·부가정보 입력) → 후보만으로
> 랙배치(현 에디터) → 배치예정 장비 **목록+가격+합산** 화면.

## 단계(phase) 매핑 — 의존 순서대로 구현·커밋
- **Phase 1 (이번): 기준정보 + Rack-Type 관리 화면** ← 지금 구현
- Phase 2: 장비 후보풀(선정) + 후보별 가격/부가정보 입력 화면 (키스톤)
- Phase 3: 배치 검색을 **후보풀로 제한** (에디터)
- Phase 4: 배치예정 장비 **목록+가격+합산** 화면

## Phase 1 Scope IN (이번 구현)
- `bombom/hierarchy.py`: `list_hierarchy(root)` — offerings/ 트리(offering→region→zone→
  rack_type, 각 노드의 표시 name + rack 수)를 디렉터리/마커 YAML에서 읽어 반환.
- API:
  - `GET /api/hierarchy` → 전체 기준정보 트리(여러 오퍼링).
  - `POST /api/hierarchy` `{level: offering|region|zone|rack_type, offering, region?, zone?,
    rack_type?, name?}` → 기존 `scaffold_*` 재사용으로 마커 생성 + 커밋. 부모 없으면 404,
    중복 409, 안전하지 않은 id 422.
  - `GET /manage` → 관리 화면(`web/manage.html`).
- `web/manage.html`: 트리 렌더 + 각 레벨 "+추가"(id + 표시 name) → POST → 새로고침. git 용어
  비노출. 에디터/대시보드 링크.
- CLI는 기존 `bombom scaffold …`로 충분(추가 안 함).
- 테스트(throwaway git repo): 생성/중복/부모없음/traversal/관리화면 제공.

## Scope OUT (이번 단계)
- 장비 후보풀·가격 입력 화면(Phase 2), 배치 후보 제한(Phase 3), 목록 화면(Phase 4).
- 노드 **삭제/이름변경/이동** — append-only(보류). 지금은 추가만.
- 전역 Rack-Type 어휘(고정 vocab) — rack_type은 자유 디렉터리라 별도 vocab 불필요.
- 권한/인증(P5).

## Constraints
- `vendor/`·카탈로그 read-only. 기존 API(/api/tree, /api/rack*, confirm, report, dashboard)
  동작 보존. git 작업은 백엔드만(사용자 비노출).
- id는 `_safe_id`(영숫자/.-_, traversal 차단). 마커 생성은 `scaffold_*` 재사용(재구현 금지).

## Exit Criteria (Phase 1)
- [ ] `POST /api/hierarchy {level:"offering", offering:"cloud-b"}` → offerings/cloud-b/
  offering.yaml 생성 + 커밋 1개; `GET /api/hierarchy`에 cloud-b 표시.
- [ ] region/zone/rack_type 생성: 부모 있으면 200, 없으면 404, 중복 409.
- [ ] `name` 지정 시 마커 yaml의 name에 반영.
- [ ] traversal/잘못된 id → 422, 파일 미생성.
- [ ] `/manage`가 트리 + 레벨별 추가 컨트롤을 렌더(에러는 메시지로).
- [ ] `pytest` 전부 통과, ruff/secrets clean.

## Risk Flags
- 빈 디렉터리는 git이 추적 못함 → 각 레벨 마커 YAML(offering/region/zone/rack-type.yaml)로
  커밋 가능하게(scaffold가 이미 생성).
- `/api/tree`는 단일 오퍼링 가정 → 관리용은 별도 `list_hierarchy`로 여러 오퍼링 처리.
- 후속 Phase에서 "후보=가격엔트리 보유 장비" 모델링 확정 예정(이번 범위 아님).
