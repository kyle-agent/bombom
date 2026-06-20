# bombom — Roadmap

> Living document. Captures personas, scope boundaries, the long-range plan, and the
> near-term backlog. Last updated: 2026-06-20.

bombom의 운영 사이클은 **설계 → 확정(승인) → 릴리즈별 BOM → 현황 조회**의 반복이다.
NetBox/Nautobot의 데이터 모델을 참고하되, 우리에게 필요한 것(배치 + 원가 + 확정 워크플로우)만
얹는다. **git이 source of truth**이므로 "확정"은 별도 DB 상태가 아니라 PR 리뷰 / 머지 / 태그로
모델링한다.

```
[카탈로그] → [한 번 설계: Rack/Rack-Type 베이스라인] ─┐
                                                     ├→ [릴리즈 N: 장비 선택·배치]
                                                     │     → [확정: PR 머지 + 태그 R26.xx]
                                                     │         → [투자대상 리스트 + BOM]
                                                     │             → [현황 대시보드 반영]
[릴리즈 N+1] ─────────────────────────────────────────┘  (반복)
```

---

## Personas (누가 쓰는가)

| 역할 | 하는 일 | 시스템에서 |
|---|---|---|
| **설계자(Designer)** | HW 선택, 랙 배치, 릴리즈별 추가 설계 | 브랜치에서 편집 → 커밋 author = 설계자 |
| **승인자(Approver)** | 설계 검토·확정 | PR 리뷰 → 머지 + 릴리즈 태그 |
| **CAPEX 소비자(재무/기획)** | 투자 금액 조회·리포트 | 대시보드 + 투자대상 리스트(Excel) |

---

## Scope — bombom이 하는 것 / 안 하는 것

**한다:** 카탈로그 기반 HW 선택, 조직 계층 배치(랙 실장), 릴리즈별 증분 설계, 확정 워크플로우,
CAPEX BOM 집계·리포트, 현황 조회.

**안 한다 (Scope OUT):**
- NetBox 대체 아님 — IPAM, 케이블/배선, 전력·열 시뮬레이션, 가상화/IP 관리 ❌
- 실시간 DCIM 모니터링·텔레메트리 ❌
- OPEX(운영비)·전력 요금 산정 ❌ (CAPEX에 집중)
- 카탈로그 스펙 직접 수정 ❌ (커뮤니티 라이브러리 read-only, 수정은 upstream PR)

---

## BOM 3종 뷰 (혼동 방지)

| 뷰 | 정의 | 용도 |
|---|---|---|
| (a) **릴리즈 증분** | 해당 릴리즈에 추가된 placement/line-item만 | "이번에 얼마 투자?" = 투자대상 리스트 |
| (b) **릴리즈 시점 스냅샷** | 릴리즈 N 태그 기준 누적 | "R26.07 시점 총 자산" |
| (c) **전체 누적 총액** | 모든 확정 placement 합 | **대시보드 헤드라인 지표** |

> **결정:** 대시보드 헤드라인은 **(c) 전체 누적 총 CAPEX**. (a) 릴리즈 증분은 보조 지표로
> 항상 같이 노출.

---

## P0 — 기반 (완료)

- 커뮤니티 카탈로그(devicetype-library) 연동, 인덱스 캐시(SQLite).
- 설계 계층 YAML: Offering → Region → Zone → Rack-Type → Rack → Device.
- BOM 엔진: pricing/ 오버레이로 CAPEX 롤업(원화).
- 웹 에디터(랙 실장도, 장비 선택·배치, 메타 입력, 저장 시 git commit), 읽기전용 뷰어.
- 가격·카테고리·메타 오버레이(카탈로그와 분리, ADR spec-cost-separation).
- 릴리즈 태그(R26.07 등), placement의 `release` 필드.
- 랙 추가 UI(POST /api/rack/new), GitHub Pages 읽기전용 export.

**Entry points:** `bombom catalog|bom|scaffold|export|serve`, `from bombom.api import create_app`.

---

## P1 — 설계 → 확정 (릴리즈 단위 + 태그 봉인)  ⟵ 구현됨 (로컬 git)

> 구현 완료: `bombom/confirm/` + `/api/confirm/*` + 에디터 확정 UI + `bombom confirm` CLI.
> 확정 = `confirmations/<id>.yaml` 매니페스트 + annotated 태그(로컬 git, GitHub 무관).
> 설계 결정: ADR `docs/decisions/2026-06-20-confirm-workflow.md`. 미구현 항목은 Scope OUT 참고.

**목표:** "확정"을 git 흐름으로 정의한다. **확정 단위 = 릴리즈.**

- 설계자는 작업 브랜치에서 릴리즈 추가분을 편집(에디터가 이미 커밋).
- **확정 = 그 릴리즈의 PR 머지 + 릴리즈 태그(R26.xx) 봉인.** 에디터에 "릴리즈 확정 요청" 액션
  → 백엔드가 PR 생성, 승인자가 머지하면 태그.
- 상태 모델: `draft`(작업중) / `in-review`(확정요청·PR open) / `confirmed`(머지+태그됨).
- **확정 게이트 체크리스트(통과해야 PR 생성):**
  - 필수 메타 0 누락
  - U 충돌 0 (실장 겹침 없음)
  - 가격 누락 → 경고(차단 여부는 P4에서 정책 확정)
- 승인 권한 분리(설계자≠승인자 강제)는 P5.

**산출물:** 릴리즈 확정 요청 API + 에디터 버튼, PR 생성 연동, 상태 뱃지, 확정 전 검증 게이트,
릴리즈 태그 자동화.

**왜 먼저인가:** "확정된 내용으로 BOM", "현황 조회"가 모두 *릴리즈 확정의 정의*에 의존한다.

---

## P2 — 릴리즈 단위 증분 설계 + 투자대상 리스트  ⟵ 구현됨

> 구현: `bombom/report/` (`investment_rows`/`investment_csv`/`release_summary`),
> `GET /api/report/invest.csv`, `bombom report invest|releases`. 투자대상 = release 태그 항목
> CSV(Excel 호환, formula-injection 방지). 외부 .xlsx 템플릿은 Scope OUT(양식 수령 후).

**목표:** 베이스라인은 한 번 설계, 매 릴리즈는 추가 장비만 선택·배치·집계.

- 베이스라인(Rack/Rack-Type, 거의 불변) vs 릴리즈별 추가 placement 분리(`release` 필드 활용).
- **장비는 append-only** — 각 릴리즈는 장비를 더하기만 한다. (제거/교체/refresh는 *향후 결정*,
  아래 Open Decisions 참고.)
- 릴리즈 라이프사이클: 릴리즈 열기 → 장비 선택·배치 → 확정(P1).
- **투자대상 리스트 산출 (BOM 뷰 a):** 해당 릴리즈에 추가된 placement / custom_line_item만
  위치(랙 경로)·장비·수량·단가·소계·합계로 **Excel/CSV 내보내기**.
- **외부 템플릿 리포트:** 재무가 정해준 양식으로 내보내기(양식 받으면 착수; 형식은 P4와 공유).
- 릴리즈 비교(diff): 직전 릴리즈 대비 증분(장비·금액).

**산출물:** 릴리즈 스코프 BOM 리포트(export), 릴리즈 diff 뷰, 릴리즈 열기/확정 CLI·API.

---

## P3 — 현황 대시보드 (조회)  ⟵ 구현됨

> 구현: `bombom/dashboard.py` (`build_dashboard`), `GET /api/dashboard`, `/dashboard`
> (`web/dashboard.html`), `bombom dashboard`. 헤드라인=누적 총 CAPEX, 계층/카테고리 롤업,
> 릴리즈 추이(증분+누적), 상위 지출 장비, 미가격/메타누락 카운트. 정적 Pages 베이킹은 후속.

**목표:** 확정된 설계의 현재 상태를 한눈에. **헤드라인 = 전체 누적 총 CAPEX(뷰 c).**

- 롤업: Offering / Region / Zone / Rack-Type별 누적 CAPEX, 장비 수량, U 사용률.
- 릴리즈별 투자 추이(누적 c + 증분 a 나란히), 상위 지출 장비, 필수 메타 미입력 현황.
- 읽기전용 뷰어를 요약 대시보드로 확장(Pages로 공유).

**산출물:** 대시보드 페이지(헤드라인 누적 CAPEX + 트리 롤업 + 릴리즈 추이), 집계 API.

---

## P4 — 가격·카탈로그 데이터 운영

- 가격북 관리: 이력, valid_from/valid_to, 벤더 견적, 통화.
- **가격 누락 정책 확정**(P1 게이트와 연결): 확정 차단 vs 경고-후-진행.
- 카탈로그 서브모듈 갱신 절차, 카탈로그에 없는 **커스텀 장비** 등록 경로.
- 외부 리포트 템플릿 매핑(재무 양식 ↔ 내부 BOM 필드).

---

## P5 — 인증·권한·배포 하드닝

- 확정 권한 분리(설계자 vs 승인자), 보호 브랜치.
- 감사추적(git 이력 활용), 사내 배포(컨테이너), 백업.

---

## 시퀀싱

P1 → P2 → P3가 주 경로(릴리즈 확정 정의가 BOM/현황을 푼다). P4/P5는 병행 가능.
각 단계 착수 전 `/brief`로 Scope OUT 잠그고, 비자명한 선택은 `/adr`로 기록한다.

## Open Decisions (확정/보류)

- **[확정]** 확정 단위 = 릴리즈 + 태그 봉인.
- **[확정]** 릴리즈 간 장비 변화 = append-only(추가만), 제거/교체는 보류.
- **[확정]** 대시보드 헤드라인 = 전체 누적 총 CAPEX(증분 보조).
- **[보류]** 장비 제거/교체/refresh(감가·retire) — 실제 HW refresh 요구가 생기면 데이터 모델
  재검토(시점 의존 BOM 필요). P2 이후.
- **[보류]** 가격 누락 시 확정 차단 vs 경고 — P4 가격 정책에서 확정.
- **[보류]** 외부 리포트 템플릿 형식 — 재무 양식 수령 후.

> P1 착수 시 위 [확정] 3건은 `/adr`로 정식 기록한다(확정 워크플로우는 load-bearing 결정).
