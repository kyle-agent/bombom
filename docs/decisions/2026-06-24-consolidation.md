# 2026-06-24 — 중복 화면 통합 + 메인 대시보드 정리 (인수인계 대비)

## Context
메인→존(place, 보기/편집 토글)→투자 리포트(summary) 흐름이 자리잡으면서, 초기 화면들이
새 흐름과 중복됐다: 뷰어(/)·랙구성도(/layout)·배치목록(/placed)·현황(/dashboard). 다른 팀에
소스를 넘길 예정이라 표면을 줄이고 일관된 흐름으로 정리할 필요가 있었다.

## Decision
- **화면 4개 제거(파일 삭제):** viewer/layout/placed/dashboard.
  - `place` 보기 모드 = 뷰어+랙구성도, `summary` = 배치목록 집계, `home` 대시보드 = 현황.
  - 루트 `/` → 메인 대시보드(home) 서빙.
  - **API 엔드포인트는 유지**: `/api/dashboard`,`/api/placed`(+csv),`/api/layout`은 리포트/CLI/
    `place`가 사용. 화면만 제거.
- **에디터(/edit) 유지 → "랙관리/확정" 역할.** 일상 배치는 place로 일원화하되, 랙 추가/복제·
  Rack Model 변경·릴리즈 확정(✅)은 에디터에만 있어 보존.
- `web/viewer.html`은 `bombom export` 템플릿으로만 잔존(화면/라우트/nav에서 제외).
- 전 페이지 nav 동일 세트로 통일. 메인 대시보드 디자인 개선(히어로 KPI + 랙타입/리전 투자비중 막대).
- 정적 빌더는 출력 디렉터리를 비우고 시작(삭제된 페이지 잔존 방지).

## Consequences
- 화면 14 → 10(+리다이렉트 zone) 로 축소, 진입 흐름이 메인/존/리포트 한 줄로 명확.
- 집계는 `build_overview` 단일 소스라 대시보드/BOM 일치 유지.
- 테스트 갱신: `/layout`·`/placed`·`/dashboard` **페이지** 라우트는 404를 기대(API는 200),
  에디터 라벨 검증 "에디터"→"랙관리".
- **Scope OUT:** `bombom export`/viewer.html 완전 폐기는 보류(필요 시 cli.py·export.py·test_web
  정리). 인수인계 문서는 `docs/HANDOFF.md`.
