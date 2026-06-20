# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

> ⏳ **PENDING — ACTION REQUIRED (user asked to be reminded):** `main` was created and pushed
> at the same commit as the feature branch (all work is on `main` too), but the repo's DEFAULT
> branch is still `claude/vibrant-tesla-okhpxz`. To finish the "merge", switch the default to
> `main`: GitHub → Settings → Branches → Default branch → `main`, or
> `gh repo edit kyle-agent/bombom --default-branch main`. (I can't change the default branch with
> the available tools.) After switching, the feature branch can be deleted (identical to `main`).

> Branch: work is on BOTH `main` and `claude/vibrant-tesla-okhpxz` (same commit). 135 tests pass, ruff clean.

## Where things are (2026-06-20)

The end-to-end designer flow is built and pushed on the feature branch, all screen-driven
(git never surfaced to users). Run `bombom serve` then:

- `/manage` — 기준정보·Rack-Type 관리 (offering/region/zone/rack-type 추가·삭제[빈 노드만]).
- `/candidates` — 장비 후보풀: 카탈로그에서 후보 선별 + 가격/부가정보 입력. (후보=별도 목록
  `candidates/pool.yaml`, 가격은 `pricing/manual.yaml`로 분리. ADR candidate-pool.) 조직이
  `meta/fields.yaml`에 `applies_to: candidate` 필드를 정의하면 후보별 **구조화 부가정보**(리드타임
  등) 입력칸이 뜨고 `candidate.meta`에 저장된다. `GET /api/candidate-fields`.
- `/search` — 전역 검색: 노드/랙/배치 장비를 이름으로 찾기(`GET /api/search`). 랙·장비 결과는
  뷰어로 딥링크.
- `/health` — 검증 대시보드: confirm 전에 검증오류·경고·미가격배치·미가격후보·후보메타누락을 한
  화면에 모아 클릭으로 수정 이동. `bombom/health.py` `build_health`(= compute_bom 이슈/unpriced +
  후보풀 갭 집계), `GET /api/health?path=`.
- `/edit` — 배치: "① 모델 선택" 검색이 후보풀만(`?pool=1`) 본다. ✅확정 모달(게이트→봉인 태그).
- `/placed` — 배치예정 장비 목록 + 합계 CAPEX + 릴리즈 필터 + CSV(전체/릴리즈별).
- `/dashboard` — 누적 총 CAPEX 헤드라인 + 계층/카테고리 롤업 + 릴리즈 추이 + 상위 지출.
- 확정 워크플로우: `bombom/confirm/` (release+build, manifest `confirmations/<id>.yaml`,
  annotated 태그). ADR confirm-workflow.
- **복제**: 에디터 `⧉ 복제`(랙→같은 Rack-Type 새 랙, 배치 그대로) + `⧉ 여러 개`(일괄 N개,
  `R10,R11`/`web-02..05` 패턴, 단일 커밋), `/manage` 노드별 `⧉ 복제`(존/타입/리전 서브트리
  통째). `POST /api/rack/clone`·`/api/rack/clone-bulk`·`/api/hierarchy/clone`. ADR clone.
- **보고서 export**: `/placed`·`/dashboard`의 `📄 보고서` → `GET /api/report.html`(데이터 구운
  standalone HTML, 인쇄/PDF). `export.build_report_data` = dashboard 롤업 + placed 행.
- **변경 비교(/diff)**: 확정 태그(=릴리즈) 또는 작업본(WORKING) 두 개를 슬롯 단위로 비교 →
  추가/제거/교체 + CAPEX 델타. `bombom/release/diff.py` `compare_releases`, `GET /api/release/
  diff?base&head&path`. release="설계 모음 확정" 정의를 구현. ADR release-diff.

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
