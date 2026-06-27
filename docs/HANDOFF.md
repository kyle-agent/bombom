# bombom 인수인계 문서

다른 팀이 이 저장소를 이어받아 개발/운영할 수 있도록 정리한 문서입니다.
설계 배경은 `docs/DESIGN.md`, 의사결정 기록은 `docs/decisions/*`(ADR)에 있습니다.

---

## 1. 한 줄 요약

**bombom**은 클라우드 인프라 설계자가 하드웨어를 골라 **Offering→Region→Zone→Rack-Type→Rack→Device**
계층으로 랙에 배치하고, 그로부터 **투자비(BOM/CAPEX)** 를 산출하는 도구입니다. 하드웨어 스펙은
NetBox 커뮤니티 `devicetype-library`를 재사용하고, bombom은 **가격 오버레이 + 조직 배치 모델 +
랙 실장도(elevation)** 를 더합니다.

## 2. 빠른 시작

```bash
pip install -e ".[dev]"                 # 런타임 + 개발(pytest/ruff/httpx) 의존성
git submodule update --init --depth 1   # vendor/devicetype-library 카탈로그
bombom catalog reindex                  # SQLite 인덱스 생성(.index/catalog.db, ~30–60s)

python scripts/showcase.py demo-ws      # 데이터가 가득 찬 데모 워크스페이스 시드
bombom serve --root demo-ws             # http://127.0.0.1:8000  (메인 대시보드)
```

- 테스트: `pytest -q` (현재 175 passed) · 린트: `ruff check bombom tests scripts`
- 프런트는 바닐라 HTML+JS. `<script>` 문법 점검: 추출 후 `node --check`.

## 3. 아키텍처

- **백엔드:** Python + FastAPI (`bombom/api/app.py`). 읽기 뷰 + 배치/기준정보 쓰기 API.
- **프런트:** 의존성 없는 단일 HTML 페이지들(`web/*.html`). 빌드 단계 없음.
- **데이터 소스 = Git이 진실.** 조직 데이터는 YAML 파일(디렉터리 트리 = 계층). 쿼리는
  **재생성 가능한 SQLite 인덱스**(`.index/catalog.db`)에서. **애플리케이션 DB 없음.**
- 하드웨어 카탈로그는 git submodule(`vendor/devicetype-library`), **읽기 전용**(직접 수정 금지).
- 가격은 `pricing/`에만, 스펙과 분리 보관(ADR spec-cost-separation).

## 4. 화면 흐름 & 라우트 (현재, 통합 후)

핵심 흐름은 **메인 → 존 → 리포트** 한 줄입니다.

| 라우트 | 파일 | 역할 |
|---|---|---|
| `/` (= `/home`) | `home.html` | **메인 대시보드** — 총 CAPEX·KPI, 랙타입별/리전별 투자비중, 존별 카드 |
| `/place?path=<zone>` | `place.html` | **존 화면** — 좌상=배치 트리, 좌하=**후보 팔레트(전체 후보풀 항상 노출)**, 우=멀티랙 실장도. **✏ 편집 토글**로 보기↔배치. 새 배치는 **미태그(DRAFT)** — 릴리즈는 여기서 안 정함 |
| `/placed?path=` | `placed.html` | **배치 목록**(2-모드). *태그 매핑*: 색 태그 칩 사전 정의 → "칠할 태그" → 행 클릭=브러시 태깅 → 랙별 `PUT /api/rack`. *금액 조회·내보내기*: 태그 필터→선택→합계(미가격 제외)→**Excel CSV**(클라이언트) |
| `/zone?path=` | `zone.html` | `/place`로 리다이렉트(구 링크 호환) |
| `/summary` | `summary.html` | **투자 리포트** — 오퍼링/리전/존/랙타입별 선택 집계 + **릴리즈 필터** + 미가격 경고 + 분포 스택바 |
| `/manage` | `manage.html` | **기준정보** — 조직 계층(오퍼링/리전/존/Rack-Type) 추가·복제·삭제 + **후보 부가정보 항목 관리**(`/api/meta/fields`) + 존별 🗺배치·⬇draw.io |
| `/candidates` | `candidates.html` | **후보풀** — 행마다 두 영역: **부가정보(우리, 편집)** = 단가·비고·후보 메타 / **원본 사양(NetBox, 읽기전용)** = `▸ 원본 사양` 펼침으로 전체 스펙. 추가 팝업도 `상세`로 전체 확인 |
| `/edit` | `editor.html` | **랙관리 · 랙타입 분류** — 전체 랙을 랙타입별 그룹 표로, 행 셀렉트로 **재분류(`POST /api/rack/move`)**. `＋ 랙 추가`=카탈로그 모델 모달. 행 `🗺 배치`·`⧉ 복제` |

> **메뉴 비노출(백엔드·라우트는 유지):** `/diff`(변경비교, `release/diff.py`),
> `/health`(검증, `health.py`), `/search`(전역검색). 내비에서만 제거 — 완전 삭제는 미정.

**캐노니컬 내비(6):** 메인 · 후보풀 · 배치 목록 · 투자 리포트 · 기준정보 · 랙관리.
전 화면 공통 디자인 시스템: Pretendard 폰트 + 흰 sticky 헤더(`class="on"` 활성) + 스켈레톤 로딩.

**핵심 CX 흐름:** 후보풀(1차 후보 + 가격·비고, 원본 스펙 확인) → 존 배치(`/place`, 후보 팔레트에서
랙으로, 새 배치는 미태그 DRAFT) → 저장 → **배치 목록(`/placed`)** 에서 릴리즈 태그 부여 →
**투자 리포트(`/summary`)** 에서 릴리즈 필터로 집계. 장비 상세: 후보풀=전체, 배치/태그=요약(`ⓘ`).

**배치 UX 요약(`/place` 편집 모드):** 좌상단 = 배치된 목록(랙→카테고리×수량, 접힘 트리),
좌하단 = **후보 팔레트(전체 후보풀, 검색 필터)**. 칩 **클릭 → 랙 빈 U칸 클릭**으로 배치(또는 드래그).
블록 **드래그=이동**, **Alt+드래그=복사**, **✕=제거**. 점선 테두리 = 미태그(DRAFT). 휠=줌, 빈 곳
드래그=팬. `💾 저장`은 랙별 `PUT /api/rack` 커밋. **릴리즈는 여기서 안 정하고 `/placed`에서 태깅.**

## 5. API 표면 (요지)

읽기:
`GET /api/overview` (메인·리포트 집계) · `/api/layout` (존 멀티랙 SVG) · `/api/rack` (단일 랙) ·
`/api/catalog/device/{slug}` (**NetBox 전체 스펙 + 요약**) · `/api/tree` · `/api/hierarchy` ·
`/api/dashboard` · `/api/placed`(+`.csv`) · `/api/health` · `/api/release/diff` · `/api/search` ·
`/api/catalog/search` · `/api/candidates`(+`/candidate-fields`) · `/api/meta/fields` ·
`/api/confirm`(+`/{id}`) · `/api/rack/elevation.svg|.drawio` · `/api/report.html` · `/api/report/invest.csv`

쓰기(데모/정적에선 비활성):
`PUT /api/rack` · `POST /api/rack/new|clone|clone-bulk` · **`POST /api/rack/move`**(랙타입 재분류) ·
`POST /api/hierarchy(/clone)` · `DELETE /api/hierarchy` · `POST /api/candidates(/...)` ·
**`POST /api/meta/fields` · `DELETE /api/meta/fields/{key}`**(후보 부가정보 항목) ·
`POST /api/confirm/request|approve`

> 집계는 단일 소스로 일원화됨: `bombom/overview.py:build_overview`(= `placed_rows` 기반)가
> 메인·리포트·존 헤더의 수치를 모두 제공하므로 대시보드/BOM과 항상 일치합니다.

## 6. 데이터 모델 & 디렉터리 레이아웃

```
offerings/<offering>/regions/<region>/zones/<zone>/rack-types/<rt>/racks/<rack>.yaml
  rack_model: { slug: <RackTypeSpec slug> }
  placements: [ { device: <slug>, position: <U>, release: <tag>, meta: {...} } ]
  custom_line_items: [ { name, qty, unit_cost, release, category } ]   # 선택
pricing/*.yaml          # { entries: [ { slug, unit_cost, valid_from?, source? } ] }
categories/overlay.yaml # slug → server|network|storage|other (실장도 색 + 메타 scope)
candidates/pool.yaml    # 후보풀 (배치 대상 + 가격/메타)
meta/fields.yaml        # 조직 커스텀 필드 정의(자산분류/시리얼/담당팀 등; 후보 부가정보 항목은 기준정보에서 관리)
confirmations/<id>.yaml # 확정(=릴리즈) manifest. 릴리즈는 git annotated tag로 봉인
vendor/devicetype-library/  # 카탈로그 submodule (읽기 전용)
.index/catalog.db       # 재생성 가능한 쿼리 인덱스 (권위 아님)
```

릴리즈 = "설계 모음 확정". `/diff`는 확정 manifest(또는 작업본 WORKING) 두 개를 비교합니다.

## 7. 정적 데모 (GitHub Pages)

- **라이브:** https://kyle-agent.github.io/bombom/
- **빌더:** `scripts/build_static_app.py` — 실제 FastAPI 앱을 내장 ASGI 클라이언트로 구동해
  모든 GET 응답을 캡처하고, 각 페이지에 `fetch` 가로채기 shim을 주입(쓰기는 토스트로 차단,
  읽기전용 배너). 페이지 간 링크는 정적 호스팅용으로 재작성. `index.html` = 메인 대시보드.
- **데이터:** `scripts/showcase.py`가 시드한 가득 찬 워크스페이스(4 오퍼링 Enterprise/Samsung/PPP/Sovereign, Samsung/kr-west1만 zone1·zone2 채움 — 9랙·119서버, 릴리즈 R25.01/R26.07).
- **배포:** `.github/workflows/pages.yml` (push 시 build_static_app → upload-pages-artifact →
  deploy-pages). 1회 설정: repo Settings → Pages → Source "GitHub Actions".

## 8. 코드 맵 (`bombom/`)

`api/app.py`(라우트) · `workspace.py`(워크스페이스 로더) · `catalog/`(카탈로그 sync/parse/index) ·
`design/`(랙 YAML 파싱·검증·쓰기) · `bom/`(BOM/CAPEX 엔진 + PriceBook) · `overview.py`(집계) ·
`dashboard.py` · `report/`(placed/invest/CSV) · `health.py` · `release/`(태그·diff) ·
`confirm/`(확정 워크플로우) · `candidates.py` · `hierarchy.py`·`scaffold/`(노드/랙 생성·복제) ·
`overlay/`(카테고리·메타) · `render/`(SVG·draw.io 실장도) · `search.py` · `export.py`(viewer bake·
report 데이터) · `gitops.py` · `cli.py`(`bombom ...`).

## 9. 설계 결정 (ADR — `docs/decisions/`)

`docs/decisions/README.md`에 색인이 있습니다. 기반 아키텍처: git-as-backend ·
library-only-catalog · spec-cost-separation · org-hierarchy · rack-type-vs-rack-model ·
quantity-from-placement · device-categorization · app-stack. 기능 결정: candidate-pool ·
confirm-workflow · clone · drawio-export · release-diff · **device-detail-and-candidate-fields**
(NetBox 상세 엔드포인트 + 후보 부가정보 항목 관리, 원본↔오버레이 분리).

> UI/IA 반복 과정의 ADR(consolidation/overview-flow/layout-view/screen-split/ux-handoff 등)은
> 최종 IA로 대체된 뒤 정리했고, 필요하면 git 이력에 남아 있습니다.

## 10. 테스트 / 품질 게이트

- `pytest -q` (**175 passed**). 라우트 스모크 `tests/test_smoke.py`, 집계 `tests/test_overview.py`,
  장비 상세·부가정보 필드 `tests/test_catalog_detail.py`, 랙 편집·이동 `tests/test_edit.py`.
- `ruff check bombom tests scripts` (clean).
- 푸시 전 게이트는 `.claude/`의 `/pre-push` 스킬(시크릿 스캔 → 테스트 → 린트 → 리뷰).
- Tier-0 규칙: 시크릿 커밋 금지, 기본 브랜치 직접 푸시 금지, 비자명 결정은 ADR 기록
  (`.claude/rules/ai-constitution.md`).
- 프런트는 빌드 없음 — 변경 후 추출한 `<script>`를 `node --check`로 문법 점검.

## 11. 한계 & 다음 작업 후보

- 정적 데모는 **읽기 전용**(쓰기 PUT/POST 차단). 실제 편집/저장은 `bombom serve`에서.
- `/api/rack/move`는 **같은 존 내** 랙타입 재분류만(존 간 이동·서브트리 rename은 미구현 —
  확정 태그·배치 경로 충돌 때문에 설계 선행 필요).
- PR 기반 확정(현재 로컬 annotated tag 봉인)은 미구현 — 확정 로직은 PR 경로 주입 가능하게 분리됨.
- `/diff`·`/health`·`/search`는 메뉴에서 빠진 상태(백엔드 유지). 완전 삭제 여부는 미정.
- (선택) `bombom export`/`viewer.html` 완전 폐기 시 `cli.py`·`export.py`·`test_web` 정리 필요.
