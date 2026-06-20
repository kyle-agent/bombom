# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

> Branch: `claude/vibrant-tesla-okhpxz` (not yet merged to main). 110 tests pass, ruff clean.

## Where things are (2026-06-20)

The end-to-end designer flow is built and pushed on the feature branch, all screen-driven
(git never surfaced to users). Run `bombom serve` then:

- `/manage` — 기준정보·Rack-Type 관리 (offering/region/zone/rack-type 추가·삭제[빈 노드만]).
- `/candidates` — 장비 후보풀: 카탈로그에서 후보 선별 + 가격/부가정보 입력. (후보=별도 목록
  `candidates/pool.yaml`, 가격은 `pricing/manual.yaml`로 분리. ADR candidate-pool.)
- `/edit` — 배치: "① 모델 선택" 검색이 후보풀만(`?pool=1`) 본다. ✅확정 모달(게이트→봉인 태그).
- `/placed` — 배치예정 장비 목록 + 합계 CAPEX + 릴리즈 필터 + CSV(전체/릴리즈별).
- `/dashboard` — 누적 총 CAPEX 헤드라인 + 계층/카테고리 롤업 + 릴리즈 추이 + 상위 지출.
- 확정 워크플로우: `bombom/confirm/` (release+build, manifest `confirmations/<id>.yaml`,
  annotated 태그). ADR confirm-workflow.
- **복제**: 에디터 `⧉ 복제`(랙→같은 Rack-Type 새 랙, 배치 그대로), `/manage` 노드별 `⧉ 복제`
  (존/타입/리전 서브트리 통째). `POST /api/rack/clone`·`/api/hierarchy/clone`. ADR clone.
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

release = "설계들의 모음을 확정한 스냅샷"(user, 2026-06-20) = annotated git tag (name = conf id).
That clarification unblocked the release-diff feature (DONE this session). Remaining:

1. **Time-aware / per-ref valuation.** The /diff CAPEX delta prices both sides with the CURRENT
   pricebook to isolate *design* change. A complementary "as-of valuation per ref" (read pricing
   at each tag) + custom_line_items in the diff unit would show price drift too. Buildable
   autonomously; lower urgency. Decommission *visibility* itself is now done (/diff shows
   removed/replaced); actual removal is editor working-tree edit.
2. **Node rename/move** in /manage (a rename moves a subtree and can collide with confirmed
   tags / placement paths; design it before building).
3. **GitHub PR-based confirm** — local annotated tag is the seal today; PR flow + server
   auth/role separation (designer≠approver enforced) is scoped OUT. Confirm logic is behind a
   thin layer to allow injecting a PR path.
4. **Structured 부가정보 on candidates** — currently a free-text note; could drive `meta/`
   fields per candidate/type. (Low-ambiguity; buildable autonomously if prioritised.)
5. **Bulk rack clone** (N copies / naming pattern in one action) — extends the clone primitive;
   scoped OUT of clone v1. Low-risk, buildable autonomously.

DONE this session: clone (rack + subtree), standalone report export, release diff (/diff),
node delete (empty-only), full placed CSV, cross-page nav.

## Blockers
None. Branch is green; merge to main is a separate explicit step (Tier-0: needs confirmation).

## Dev
`pip install -e .`; tests `pytest -q` (95 pass); lint `ruff check bombom tests`. Fresh clone:
`git submodule update --init` then `bombom catalog sync && bombom catalog reindex` (~47s).
Frontend pages are vanilla HTML+JS; syntax-check via `node --check` on the extracted <script>.
