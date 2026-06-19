# 브리프: 용어 정리 (Rack-Type=용도 / Rack Model=물리) + 랙 모델 picker

**목표**
계층 용어를 **Offering → Region → Zone → Rack-Type(용도) → Rack**로 정리하고, 카탈로그 물리 랙을
**Rack Model**로 분리 명명한다. 화면/CLI에서 **Rack Model을 고르는 picker**를 추가한다.

## 용어 매핑
- 계층 레벨 (Zone 아래 그룹) : `rack-groups/` → **`rack-types/<control|data|storage|network>/`**.
  용도(purpose)는 **디렉터리 레벨**에서 옴 (rack YAML의 `role` 필드 제거).
- 카탈로그 물리 랙 참조 : rack YAML `rack_type:` → **`rack_model:`** (CatalogRef, 예 vertiv-vr3300).
- **카탈로그 패키지는 불변**: `RackTypeSpec`, `get_rack_type`, kind="rack", `vendor/`는 그대로
  (NetBox 물리 랙 정의 자체).

## Scope IN
- design 레이어 리네임: `RackDesign.rack_type`→`rack_model`, `role` 제거; loader 마커
  `rack-groups`→`rack-types`(키 `rack_group`→`rack_type`); validate/writer/svg 반영.
- 용도(purpose)는 `hierarchy["rack_type"]`(디렉터리)에서 → engine/export의 meta scope(role:)와
  카테고리 집계에 사용.
- scaffold: `scaffold rack-type` (구 rack-group), `scaffold rack … --rack-model <slug>`.
- **Rack Model picker**: `/api/catalog/search?kind=rack` 추가(카탈로그 rack 65종 검색);
  에디터에 "Rack Model 고르기" UI; 선택 시 `rack_model` 설정·U높이 갱신.
- export/뷰어/에디터 트리 키 `rack_groups`→`rack_types`, 라벨 "Rack Group"→"Rack-Type",
  헤더 rack_type→rack_model.
- 샘플 데이터 이동: `…/rack-groups/row-3/racks/R02.yaml` → `…/rack-types/data/racks/R02.yaml`
  (`rack_model:` 사용, `role` 제거).
- 문서/메모리/ADR 용어 갱신(+ 새 ADR: 용어 확정).

## Scope OUT
- 카탈로그 패키지/`vendor/` 변경(불변).
- 브라우저 직접 커밋(Decap)·Pages 편집(이전 결정 유지).
- 다중 offering 트리(뷰어는 단일 offering 유지).

## Constraints
- `bombom/catalog/**`, `vendor/**` 읽기전용. git=원본. 테스트 전부 green 유지.
- 리네임 일관성: `rack_type`(카탈로그/물리) 잔재가 설계 레이어에 남지 않게.

## Exit Criteria
- [ ] 디렉터리가 `…/zones/<z>/rack-types/<type>/racks/<rack>.yaml`; rack YAML은 `rack_model:` 사용,
  `role` 없음. `bombom bom offerings/cloud-a` = ₩84,220,000 그대로.
- [ ] `bombom scaffold rack-type …`, `scaffold rack … --rack-model <slug>` 동작.
- [ ] `/api/catalog/search?kind=rack&q=vertiv` 가 카탈로그 랙(예 vertiv-vr3300) 반환.
- [ ] 에디터에서 Rack Model을 검색·선택하면 `rack_model`이 바뀌고 저장 시 YAML/커밋 반영.
- [ ] 뷰어/에디터 트리가 Rack-Type(용도)별로 랙을 묶어 표시.
- [ ] `pytest` 전부 통과(리네임 반영), ruff/secrets clean.

## Risk Flags
- 광범위 리네임 → 카탈로그(물리 rack) 개념과 혼동 금지: 설계=rack_model, 카탈로그=RackTypeSpec.
- 용도를 디렉터리에서만 → meta scope(role:)·카테고리 집계가 hierarchy 값을 쓰도록 빠짐없이 교체.
- 프론트(viewer/editor) 트리 키 변경 누락 시 화면 깨짐 → 키 일괄 교체 + export 검증.
