# Session Handoff — LATEST

> Forward-looking only. This is "what to do next", not "what was done". Rewritten by
> `/session-checkpoint` at the end of each session. Git history preserves old state.

> Branch: `claude/vibrant-tesla-okhpxz` (not yet merged to main). 95 tests pass, ruff clean.

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

Key modules: `bombom/{confirm,candidates,hierarchy,dashboard}.py`, `bombom/report/`,
endpoints in `bombom/api/app.py`, pages in `web/{manage,candidates,placed,dashboard}.html`.
Live price refresh: writing a price reloads the shared `ws.pricebook` so all views update
without a restart.

## Priority — pick next

1. **Decommission / 장비 교체·제거.** Everything is append-only today; placed devices and
   confirmed tags are immutable. Removing/replacing a placed device needs a model decision
   (supersede vs delete) and likely time-aware BOM. Revisit ADR candidate-pool override note.
2. **Node rename/move** in /manage (deferred this session — a rename moves a subtree and can
   collide with confirmed tags / placement paths; design it before building).
3. **GitHub PR-based confirm (P5)** — local annotated tag is the seal today; PR flow + server
   auth/role separation (designer≠approver enforced) was scoped OUT. Confirm logic is behind a
   thin layer to allow injecting a PR path.
4. **Structured 부가정보 on candidates** — currently a free-text note; could drive `meta/`
   fields per candidate/type.
5. **Static export of dashboard/placed** for Pages sharing (viewer export exists; these are
   live-only).

## Blockers
None. Branch is green; merge to main is a separate explicit step (Tier-0: needs confirmation).

## Dev
`pip install -e .`; tests `pytest -q` (95 pass); lint `ruff check bombom tests`. Fresh clone:
`git submodule update --init` then `bombom catalog sync && bombom catalog reindex` (~47s).
Frontend pages are vanilla HTML+JS; syntax-check via `node --check` on the extracted <script>.
