# 2026-06-20 — 확정(Confirm) 워크플로우: 로컬 git, 화면 기반, release+build 공통

## Context
설계가 끝나면 "확정"하고, 확정된 내용으로 BOM을 뽑고 현황을 본다(ROADMAP P1). 두 가지 확정
트리거가 있다: (1) **릴리즈 확정** — 기존 랙에 매 릴리즈 장비를 추가, (2) **신규 빌드 확정** —
기존 설계를 clone해 새 오퍼링을 만들어 릴리즈 일정과 **병행** 출시. 사용자 중 다수는 git을
모르므로 전 과정이 화면으로 가능해야 한다.

## Decision
- **확정 = 검토된 변경셋을 annotated git 태그로 봉인.** git이 source of truth이므로 별도 DB
  상태가 아니라 태그 + 매니페스트로 표현한다.
- **메커니즘 = 로컬 git.** GitHub PR/머지/토큰에 의존하지 않는다. 확정요청은 매니페스트를
  in-review로 쓰고, 확정은 매니페스트를 confirmed로 쓴 뒤 annotated 태그를 단다. 리뷰는 앱 내
  변경셋 요약(영향 랙·추가 장비·금액)으로 하며 git diff를 노출하지 않는다.
- **release와 build를 `kind`로 구분하되 한 워크플로우를 공유** — 같은 게이트·상태머신·태그.
  - `kind=release` → `scope.release`; 영향 랙 = 그 릴리즈 placement를 가진 랙(변경셋은 그 릴리즈
    placement만 = 투자대상).
  - `kind=build` → `scope.paths`; 영향 랙 = 그 경로 하위 전체.
- **상태 저장 = `confirmations/<id>.yaml`** 매니페스트:
  `{id, kind, scope, status: draft|in-review|confirmed, requester, approver, created_at,
  confirmed_at, tag}`. 신규 최상위 디렉터리, git 추적.
- **확정 게이트**(영향 랙만, 기존 `validate_rack`+`required_missing` 재사용): 필수 메타 누락=error,
  U충돌/구조오류=error, 가격 미등록=warning(비차단). error 0일 때만 in-review/confirmed 진행.
- **사용자는 git 비노출** — commit·tag·매니페스트 쓰기는 전부 백엔드. UI는 도메인 언어(상태·장비·
  금액)만 쓴다.
- **append-only + 불변 태그** — confirmed 태그는 immutable. 이후 변경은 새 confirmation/release.
  같은 태그 재생성은 거부.

## Alternatives considered
- **GitHub PR 연동(앱이 PR 생성→머지 감지→태그).** 강력하고 리뷰·감사추적을 GitHub에 위임하지만
  서버측 토큰/인증 인프라가 선행돼야 하고, git을 모르는 사용자에게 PR 흐름이 노출된다. → P5로 미룸.
  확정 로직을 인터페이스 뒤에 두어 나중에 PR 경로를 주입할 수 있게 한다.
- **상태를 git만으로(태그=confirmed, 브랜치=in-review).** 추가 파일이 없지만 requester/approver/
  사유/시각 같은 메타를 표현하기 어렵다. → 매니페스트 채택.
- **릴리즈 매니페스트만(releases/<R>.yaml).** 릴리즈 확정엔 맞지만 clone 기반 신규 빌드 확정을
  담지 못한다. → 일반 `confirmations/` 채택.
- **확정 단위를 릴리즈로 한정.** 신규 오퍼링이 릴리즈와 병행 출시되는 실제 시나리오를 못 담는다.
  → `kind`로 일반화.

## Consequences
- 신규 패키지 `bombom/confirm/`: 매니페스트 모델 + 게이트 + request/approve(=write+commit+tag).
- API: `POST /api/confirm/request`, `POST /api/confirm/approve`, `GET /api/confirm`,
  `GET /api/confirm/{id}`. 에디터에 확정요청/대기목록/확정 UI. CLI `bombom confirm …`.
- BOM/현황은 confirmed 태그(또는 매니페스트)를 기준 ref로 읽을 수 있다(P2/P3에서 활용).
- 게이트는 영향 랙으로만 한정해 대형 트리에서도 비용을 억제한다.

## Override conditions
사내 배포에서 승인 권한 분리·감사추적 요구가 강해지면 GitHub PR 연동(P5)으로 확정 메커니즘을
교체/병행한다(인터페이스는 그대로). 장비 제거/교체(decommission)가 필요해지면 append-only 가정과
시점 의존 BOM을 재검토한다.
