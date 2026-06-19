# 브리프: 실제 동작 뷰어 + 기초데이터 입력 + 디바이스 메타(커스텀 필드)

**목표**
mock을 실데이터로 동작하는 화면으로 만든다 — 카탈로그/설계/원화 BOM을 NetBox식 랙 SVG로 보여주는
FastAPI 백엔드와 뷰어, 기초데이터(계층)를 CLI로 생성·복제하는 수단, 카테고리 오버레이, 디바이스
메타(커스텀 필드: 타입+인스턴스, 조건부 필수), 릴리즈↔git(경량)을 추가한다.

## Scope IN
- **기초데이터 입력(CLI)**: `bombom scaffold offering|region|zone|rack-group|rack <…>` 가 올바른
  경로에 YAML 스켈레톤 생성; `bombom scaffold clone <기존경로> <새이름>` 서브트리 복제+식별자 치환.
- **카테고리 오버레이**: `categories/overlay.yaml`(slug→category) + 휴리스틱 폴백;
  `bombom category set <slug> <cat>`. 카탈로그 검색·BOM `by_category`가 사용.
- **디바이스 메타 / 커스텀 필드**:
  - 정의 `meta/fields.yaml`: `{key,label,type(string|int|enum|bool|date),options?,required,
    applies_to(device_type|placement),scope(all|category:X|role:Y)}`.
  - 타입값 오버레이 `meta/devicetypes/<vendor>.yaml`(slug→필드값), 카탈로그와 분리.
  - 인스턴스값: 랙 YAML `placements[].meta{}`.
  - 합성(카탈로그+타입메타+placement.meta) + **조건부 필수 검증**(category/role scope에 맞는
    required 누락 → issue). `bombom meta set-type <slug> k=v`, `bombom meta fields`(정의 출력).
- **FastAPI 백엔드** `bombom/api/`: `/api/tree`, `/api/catalog/search`, `/api/bom?path=&release=`,
  `/api/rack/elevation.svg?path=`(서버 렌더 SVG), 정적 프론트 서빙. `bombom serve`.
- **뷰어 프론트** `web/`: 트리 → 랙 SVG 실장도 → 장비 리스트(+메타 컬럼) + 원화 BOM + 릴리즈 필터 + 줌.
- **정적 내보내기(보기용)** `bombom export <out.html>`: 실데이터(트리·설계·메타·카탈로그 부분·BOM·SVG)를
  한 파일에 구워 서버 없이 열람.
- **릴리즈↔git(경량)**: `bombom release list`(git 태그), `bombom release tag <name>`. 델타는 placement
  태그 기준(기존).

## Scope OUT
- 웹에서 드래그-배치 편집 후 YAML 기록/커밋(이번엔 뷰어 + CLI 입력).
- 두 git ref/태그 간 BOM diff(릴리즈 델타는 태그 필터로).
- 인증/멀티유저/배포 호스팅, OPEX/TCO, 다중통화.
- 메타 필드 타입의 고급 검증(정규식/범위 등)·UI 위젯 커스터마이즈(기본 입력만).

## Constraints
- `bombom/catalog/**`, `vendor/**` 읽기전용 재사용. 가격/카테고리/메타/설계는 각자 오버레이로 분리(ADR).
- git이 원본; API는 이번엔 **읽기 전용**(쓰기는 CLI). 새 의존성 `fastapi`,`uvicorn`.

## Exit Criteria
- [ ] `bombom scaffold offering demo` → 유효 YAML 생성, `bombom bom offerings/demo` 오류 없이 동작.
- [ ] `bombom scaffold clone .../zones/az1 az2` 가 서브트리 복제 후 새 경로로 로드됨.
- [ ] `bombom category set dell-poweredge-r760 server` 후 BOM `by_category`·검색에 반영.
- [ ] `meta/fields.yaml`에 `applies_to:placement, scope:category:server, required:true` 필드 정의 +
  서버 배치에 값 누락 → BOM/검증이 해당 placement를 **메타 누락 issue**로 보고; 값 채우면 사라짐.
- [ ] `bombom meta set-type dell-poweredge-r760 asset_class=compute` 가 타입 오버레이에 기록되고 합성됨.
- [ ] `bombom serve` 후 `/api/bom?path=offerings/cloud-a`=₩84,220,000, `/api/rack/elevation.svg?path=…`
  가 SVG(랙 높이·U 위치 반영) 반환.
- [ ] `bombom export /tmp/out.html` → 브라우저로 열면 트리·랙 SVG·원화 BOM·릴리즈 필터·메타 컬럼이
  실데이터로 보임(서버 불필요).
- [ ] `pytest` 로 scaffold·category·meta(조건부 필수)·api(TestClient)·svg·release 커버 — 전부 통과.

## Risk Flags
- 범위 큼 → 동작하는 수직 슬라이스로 진행, 미완은 정직 표기.
- 원격 환경 `serve` 직접 열람 불가 가능 → 정적 export가 1차 보기 경로.
- meta scope(category/role) 평가: category는 오버레이/휴리스틱, role은 랙 `role` 필드 — 둘 다 없을 때
  required 판정 기준 정의 필요(없으면 'all'만 필수).
- 조인 키 일관성(device slug) 재사용; 카탈로그 패키지 수정 금지.
