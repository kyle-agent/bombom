# Brief: 확정 워크플로우 (Confirm — gate → 화면 리뷰 → tag 봉인, 로컬 git · git 비노출)

> Locked 2026-06-20. Roadmap P1. Decisions recorded in
> `docs/decisions/2026-06-20-confirm-workflow.md`.

## Goal
설계자가 작업한 변경(릴리즈 추가분 또는 신규 빌드)을 **화면만으로** 확정 게이트(필수 메타
0누락·U충돌 0·가격누락 경고) 통과 후 in-review로 올리고, 승인자가 **화면에서** 변경셋을 리뷰하고
"확정"을 누르면 백엔드가 `confirmations/<id>.yaml` 매니페스트 갱신 + annotated git 태그로
봉인한다. 사용자는 git 명령·태그·PR을 전혀 다루지 않는다. release와 build(clone 신규 오퍼링)는
`kind`로 구분하되 같은 게이트·상태머신·태그 기계를 공유한다.

## Scope IN
- `confirmations/<id>.yaml` 매니페스트 모델 + 읽기/쓰기 (`bombom/confirm/`):
  `{id, kind: release|build, scope, status: draft|in-review|confirmed, requester, approver,
  created_at, confirmed_at, tag}`.
  - `kind=release` → `scope.release: R26.07`; 영향 랙 = 그 릴리즈 placement를 가진 모든 랙.
  - `kind=build` → `scope.paths: [offerings/cloud-b]`; 영향 랙 = 그 경로 하위 모든 랙.
- 확정 게이트(영향 랙만, 기존 `validate_rack` 재사용): 필수 메타 누락=error, U충돌=error,
  가격 누락=warning(비차단).
- API: `POST /api/confirm/request`, `POST /api/confirm/approve`, `GET /api/confirm`,
  `GET /api/confirm/{id}`(상세=status·scope·게이트 errors/warnings·변경셋(영향 랙 + 추가 장비 +
  scope CAPEX)).
- 에디터 UI 전 과정(핵심): 설계자 "확정 요청"(게이트 결과 화면, 누락 클릭→해당 랙 이동),
  승인자 "확정 대기" 목록+변경셋 리뷰+"확정" 버튼, 상태 뱃지, 확정 태그명 화면 표시.
- CLI 패리티: `bombom confirm request|approve|list|show`.
- 테스트(throwaway git repo) + UI 흐름 점검.

## Scope OUT
- GitHub PR 생성·머지·머지 감지 — P5(로컬 태그가 봉인 수단).
- 서버측 인증/권한 분리(설계자≠승인자 강제) — P5(P1은 기록만).
- 멀티 브랜치 머지(`confirmed` 브랜치 등) — P1은 태그만.
- 장비 제거/교체/decommission — append-only(보류).
- 외부 템플릿 Excel 리포트 — P2/P4.
- git diff/patch 형태 리뷰 — 변경셋은 사람이 읽는 요약(랙·장비·금액)으로.

## Constraints
- 사용자는 git을 다루지 않는다 — commit·tag·매니페스트는 전부 백엔드, UI에 git 용어 비노출.
- `vendor/devicetype-library/` 수정 금지(read-only). `confirmations/`는 신규 최상위 디렉터리.
- 재사용: `validate_rack`·`load_racks`·`tag_release`·`add_commit` 재구현 금지.
- 기존 `PUT /api/rack`, `/api/bom`, `export`, 랙 추가 흐름 동작 변경 없음.
- 확정 로직은 인터페이스 뒤에 두어 향후 GitHub PR(P5) 주입 가능.

## Exit Criteria
- [ ] 깨끗한 릴리즈로 "확정 요청" → git 명령 없이 status=in-review, `confirmations/R26.07.yaml`
  생성 + 커밋 1개 증가.
- [ ] 필수 메타 누락 랙 포함 시 "확정 요청" → 화면에 누락 항목 표시(클릭→장비 이동);
  매니페스트 미생성·커밋 0.
- [ ] in-review 확정에 "확정" → status=confirmed·approver·confirmed_at, `git tag`에 annotated
  태그 존재, 커밋 1개 증가.
- [ ] `kind=build`로 clone된 경로(`offerings/cloud-b`)에 대해 request→approve 성공, tag 채워짐.
- [ ] in-review 아닌 id를 approve → 4xx, 태그 미생성.
- [ ] `GET /api/confirm/{id}`가 영향 랙 + scope CAPEX + 가격누락 warnings 반환.

## Risk Flags
- 비-git 사용자를 위해 게이트 실패가 수정 가능한 형태(어느 랙·장비·필드)로 화면에 떠야 함.
- 로컬 "확정=태그"가 향후 GitHub PR 모델과 갈릴 수 있음 → 확정 로직 인터페이스 분리.
- confirmed 태그는 immutable; 이후 변경은 새 confirmation/release(append-only). 재확정 거부.
- release·build 병행 시 scope 경로 겹침 가능 → P1은 겹침 감지 안 함(감시 항목).
- 대형 트리 게이트 비용 → 영향 랙으로만 한정.
