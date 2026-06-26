# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

> ⏳ **PENDING — ACTION REQUIRED (user asked to be reminded):** `main` was created and pushed
> at the same commit as the feature branch (all work is on `main` too), but the repo's DEFAULT
> branch is still `claude/vibrant-tesla-okhpxz`. To finish the "merge", switch the default to
> `main`: GitHub → Settings → Branches → Default branch → `main`, or
> `gh repo edit kyle-agent/bombom --default-branch main`. (I can't change the default branch with
> the available tools.) After switching, the feature branch can be deleted (identical to `main`).

> Branch: `claude/vibrant-tesla-okhpxz`. 168 tests pass, ruff clean. Static demo →
> https://kyle-agent.github.io/bombom/ (Pages workflow builds `web/*.html` via
> `scripts/build_static_app.py --out public`).

## Where things are (2026-06-26)

화면 IA가 **계층 한 단계씩** 정리됨 (ADR `2026-06-26-screen-responsibility-split.md`).
**hi-fi 디자인 핸드오프 반영 완료** (ADR `2026-06-26-ux-design-handoff.md`): 전 화면 Pretendard
폰트 + 캐노니컬 흰 헤더(`class="on"` 활성, `#cxbar`/active-script 제거됨) + 스켈레톤 로딩 +
상태색 토큰 통일. 캐노니컬 내비: `메인 · 후보풀 · 배치 목록 · 투자 리포트 · 기준정보 · 랙관리`.
Run `bombom serve` then:

- `/` (home.html) — **메인 대시보드**. ① 오퍼링→리전→존 구조(빈 노드 포함, 존 칩→`/place`),
  ② 랙타입별/리전별/오퍼링별 투자 막대, KPI=전체 랙·서버·리전·존 수. 검은 총액 히어로 없음.
  `GET /api/overview?path=offerings`.
- `/candidates` — **후보풀**: 등록된 후보를 카테고리(server/network/storage/other)별 목록으로
  보여주고 **인라인 가격 입력** + 비고/메타 필드. `＋ 후보 추가`는 카탈로그 검색 팝업(85+ 결과).
  후보=`candidates/pool.yaml`, 가격=`pricing/`. `GET /api/candidate-fields`.
- `/edit` — **랙관리 · 랙타입 분류**(재설계). 전체 랙을 **랙타입별 그룹 표**로 보여주고 각 행의
  **랙타입 셀렉트**로 재분류 → `POST /api/rack/move`(같은 존 내 rack-type 디렉터리 이동, 검증·
  롤백·단일 커밋; `scaffold.move_rack`). `＋ 랙 추가`=카탈로그(`kind=rack`) 모델 모달(존+타입+모델+
  ID → `POST /api/rack/new`). 행 작업 `🗺 배치`(→`/place`)·`⧉ 복제`. `GET /api/layout?path=`.
- `/place` — **배치**: 한 존의 랙들. 보기/편집 토글, 팔레트=후보풀 전체, 신규 배치는
  `release="DRAFT"`(미태그). (랙관리·기준정보에서 진입.)
- `/placed` — **배치 목록**(재설계, 2-모드). *태그 매핑*: 색 태그 칩 사전 정의 → "칠할 태그" 선택
  → 행 클릭=브러시 태깅(다중선택 일괄) → 랙별 `PUT /api/rack`(release만). *금액 조회·내보내기*:
  태그 필터→선택→**선택 합계 금액**(미가격 제외)→**Excel CSV**(클라이언트 Blob). 금액=placement
  `unit_cost`. `GET /api/layout?path=` + 랙별 `GET /api/rack`.
- `/summary` — **투자 리포트**: 오퍼링/리전/존/랙타입 그룹 집계 + 릴리즈 필터
  (`/api/overview?release=`).
- `/manage` — **기준정보**: 조직 계층(오퍼링·리전·존·랙타입) 골격만. 상단 카운트 스트립 +
  역할 분리 안내. 노드 추가·삭제(빈 노드)·서브트리 복제. `/api/hierarchy`.
- 확정 워크플로우 `bombom/confirm/`, 보고서 export `GET /api/report.html`은 백엔드 유지.
- **메뉴 비노출(백엔드는 유지):** `/diff`(변경 비교, `bombom/release/diff.py`), `/health`(검증,
  `bombom/health.py`), `/search`(전역 검색). 라우트·테스트 살아있음. 완전 삭제는 사용자 확인 후.

### 이번 세션 핵심 수정
- `build_overview`가 트리(`list_hierarchy`)는 **`ws.root`**, 배치 집계는 **넘어온 노드 경로**로
  분리해서 읽도록 고침. 이전엔 같은 인자를 둘 다에 써서 API 경유 시 트리가 비었음
  (정적 데모 메인 구조가 안 보이던 버그). `bombom/overview.py:50`.
- `scripts/showcase.py` 데모 구조: 4 오퍼링(Enterprise/Samsung/PPP/Sovereign) × kr-east1/kr-west1,
  **Samsung/kr-west1만 zone1·zone2**(랙 채워짐). 태그 R25.01/R26.07.

Key modules: `bombom/{confirm,candidates,hierarchy,dashboard}.py`, `bombom/report/`,
endpoints in `bombom/api/app.py`, pages in `web/{manage,candidates,placed,dashboard}.html`.
Live price refresh: writing a price reloads the shared `ws.pricebook` so all views update
without a restart.

## Priority — pick next

Most autonomous-buildable items are now DONE (per-ref valuation, search, candidate meta).
Remaining needs a USER decision or is heavier:

2. **Node rename/move** in /manage (a rename moves a subtree and can collide with confirmed
   tags / placement paths; design it before building).
3. **GitHub PR-based confirm** — local annotated tag is the seal today; PR flow + server
   auth/role separation (designer≠approver enforced) is scoped OUT. Confirm logic is behind a
   thin layer to allow injecting a PR path.
4. **Custom line items in the release diff** — the /diff unit is (rack, position) device slots;
   custom_line_items aren't diffed yet. Buildable autonomously if wanted.

DONE this session: clone (rack + subtree + bulk N), standalone report export, release diff
(/diff) + per-ref valuation, workspace search (/search), structured candidate fields
(meta applies_to: candidate), validation dashboard (/health), node delete (empty-only),
full placed CSV, cross-page nav.

Next feature ideas (offered to user; not yet picked): power/thermal budget per rack+zone
(reuse bom power_w), physical-fit validation (weight/depth/connector vs rack), rack template
library, bulk price import (CSV), OPEX/TCO overlay, elevation color-by-release.

## Blockers
None. Branch is green; merge to main is a separate explicit step (Tier-0: needs confirmation).

## Dev
`pip install -e .`; tests `pytest -q` (95 pass); lint `ruff check bombom tests`. Fresh clone:
`git submodule update --init` then `bombom catalog sync && bombom catalog reindex` (~47s).
Frontend pages are vanilla HTML+JS; syntax-check via `node --check` on the extracted <script>.
