# 브리프: 웹 편집 → YAML 저장 → git 커밋 + 메타 입력 폼 강화

**목표**
뷰어를 양방향 에디터로 만든다 — 설계자가 화면에서 장비를 배치/이동/삭제하고 인스턴스 메타를 입력하면,
백엔드가 검증 후 랙 YAML로 저장하고 git 커밋한다. 메타 입력은 필드 타입별 위젯 + 조건부 필수 검증.

## Scope IN
- **직렬화기** `bombom/design/writer.py`: `RackDesign → YAML` (rack_type/role/placements(meta 포함)/
  custom_line_items 보존). 원자적 쓰기.
- **git 커밋 헬퍼** `bombom/gitops.py`: `add_commit(paths, message, cwd)` — argv 기반(no shell),
  현재 브랜치에 커밋. 메시지 가드.
- **쓰기 API**: `PUT /api/rack?path=<rack.yaml>` (JSON 본문=랙 설계 전체 치환) →
  ① 스키마 검증(pydantic) ② 구조 검증(slug 존재/U 범위/중복) — 구조 오류면 **400, 미저장/미커밋** ③
  통과 시 YAML 저장 + git 커밋(메시지 파라미터) ④ 갱신된 랙 데이터 반환. 메타 필수 누락은 경고로
  반환하되 저장 허용(초안).
- **에디터 프론트** `web/editor.html` (serve 시 `/`): 트리·랙 실장도에서 **배치/이동/삭제**, 카탈로그
  검색으로 추가, **메타 입력 폼(필드 타입별 위젯: enum=select, bool=checkbox, date=date, int=number,
  string=text; 필수 표시·검증)**, 저장→PUT(+커밋 메시지), 실시간 원화 BOM.
- 정적 export(`web/viewer.html`)는 **읽기전용 유지**.

## Scope OUT
- UI에서 브랜치/PR 생성·전환 (현재 브랜치에 커밋만).
- 멀티유저 잠금/충돌 해결.
- UI에서 계층(offering/region/zone/rack-group) 편집 (scaffold CLI 사용).
- UI에서 **타입 메타** 편집 (CLI `meta set-type` 유지; UI는 인스턴스 메타만).
- 인증/권한, OPEX/TCO.

## Constraints
- `bombom/catalog/**`, `vendor/**` 읽기전용. 쓰기는 `offerings/**` 랙 파일 + git만. 가격/카테고리/메타
  오버레이 분리 유지(ADR).
- 쓰기 경로는 워크스페이스 root 하위의 `.../racks/*.yaml`로 제한(경로 traversal 차단, 직전 리뷰 교훈).
- 저장 전 `validate_rack` 재사용; 구조 오류 시 파일/커밋 변경 없음.

## Exit Criteria
- [ ] 유효 설계로 `PUT /api/rack?path=…` → 랙 YAML이 갱신되고 **git HEAD가 1개 진행**(커밋 생성);
  재조회 시 변경 반영. (tmp git repo 테스트)
- [ ] 중복 U/존재하지 않는 slug/U 범위 초과로 PUT → **400**, 파일 unchanged, 커밋 없음.
- [ ] `RackDesign` 직렬화→로드 라운드트립이 placements(meta)·custom_line_items·role·rack_type를 보존.
- [ ] 인스턴스 메타를 저장하면 placement.meta에 기록되고, BOM의 meta_missing에서 사라짐(필수 충족 시).
- [ ] 에디터: 메타 폼이 필드 타입별 위젯을 렌더(enum=select 등), 필수 미입력 시 시각 표시.
- [ ] `pytest`로 writer 라운드트립·PUT 저장+커밋·PUT 거부(구조오류)·메타 저장 커버 — 전부 통과.

## Risk Flags
- 테스트가 실제 repo를 커밋하면 안 됨 → tmp `git init` 워크스페이스에서 add_commit 실행.
- YAML 라운드트립에서 메타 값 타입 보존(enum/bool/date) — 문자열 강제 금지, 그대로 저장.
- 쓰기 경로 안전성(traversal) — root+racks/ 하위만 허용, 그 외 400.
- 저장 후 인덱스/BOM 재계산은 파일 기준이라 추가 동기화 불필요(git=원본).
