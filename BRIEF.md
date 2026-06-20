# Brief: P2 투자대상 리스트/릴리즈 요약 + P3 현황 대시보드

> Locked 2026-06-20. Roadmap P2/P3. 결정은 ROADMAP(BOM 3종 뷰, 헤드라인=누적 총 CAPEX,
> append-only)와 ADR들을 따른다.

## Goal
(P2) 확정/설계된 내용에서 **릴리즈 투자대상 리스트(BOM 뷰 a)** 를 CSV로 내보내고, **릴리즈별
증분/누적 요약**을 산출한다. (P3) 전체 현황을 **헤드라인=전체 누적 총 CAPEX(뷰 c)** 로 보는
**읽기전용 대시보드**(계층 롤업·카테고리·릴리즈 추이·상위 지출 장비·미가격/메타누락 카운트)를
추가한다.

## Scope IN
- 엔진 확장(하위호환): `LineItem`에 `rack_path` 추가(계층 롤업용; 기본 "").
- `bombom/report/`:
  - `investment_rows(ws, root, release)` → 그 릴리즈 line item(경로·Rack-Type·장비·slug·카테고리·
    수량·단가·소계·release) — `compute_bom(release=…)` 재사용.
  - `investment_csv(rows)` → CSV 문자열(UTF-8 BOM, Excel 호환).
  - `release_summary(ws, root)` → 릴리즈별 `{release, count, increment_capex, cumulative_capex}`.
- `bombom/dashboard.py`: `build_dashboard(ws, path)` →
  `{headline_capex, by_level{region,zone,rack_type}, by_category, release_summary,
  top_devices, counts{devices,unpriced,meta_missing}}` (compute_bom + parse_hierarchy 재사용).
- API: `GET /api/report/invest.csv?path&release`(text/csv 첨부), `GET /api/dashboard?path`,
  `/dashboard`(읽기전용 HTML).
- `web/dashboard.html`: 헤드라인 카드 + 계층 롤업 + 카테고리 + 릴리즈 추이(증분+누적) +
  상위 지출 장비 + 경고 카운트. KRW 포맷, XSS escape.
- CLI: `bombom report invest <release> [--path] [--out]`, `bombom report releases [--path]`,
  `bombom dashboard [--path]`.
- 테스트(report CSV·release_summary·dashboard 집계).

## Scope OUT
- 외부 템플릿 Excel(.xlsx) 양식 리포트 — 재무 양식 수령 후(P4). 지금은 일반 CSV.
- 대시보드 정적 export(Pages 베이킹) — 후속(우선 로컬 serve로 확인).
- 장비 제거/교체(decommission)·시점 의존 BOM — append-only(보류).
- ref-to-ref git diff — append-only에서 릴리즈 증분 = release 태그 항목으로 충분.
- 권한/인증 — P5.

## Constraints
- `vendor/`·카탈로그 read-only. 기존 `compute_bom` 의미·기존 API/뷰어/에디터/confirm 동작 보존.
- `LineItem.rack_path`는 기본값 있는 추가 필드로만(기존 호출부 깨지지 않게).
- 가격은 pricing/ 오버레이만, 도메인 언어로 표기(₩). 미가격은 ₩0 처리 금지(별도 카운트).

## Exit Criteria
- [ ] `GET /api/report/invest.csv?release=R26.07&path=offerings/cloud-a` → 그 릴리즈 항목만,
  헤더+행+소계, total 행 포함 CSV 반환(Content-Disposition attachment).
- [ ] `bombom report releases` → 릴리즈별 증분/누적 CAPEX 표 출력.
- [ ] `GET /api/dashboard?path=offerings/cloud-a` → headline_capex가 그 서브트리 누적 총
  CAPEX와 일치, by_level/by_category/release_summary/top_devices/counts 포함.
- [ ] `/dashboard`가 헤드라인 누적 CAPEX와 롤업/추이/상위장비/경고 카운트를 화면에 렌더.
- [ ] 미가격 장비는 counts.unpriced로, 필수 메타 누락은 counts.meta_missing으로 집계(₩0 합산 안 함).
- [ ] `pytest` 전부 통과, ruff/secrets clean.

## Risk Flags
- `by_rack`는 rack_id(stem) 키라 동명 랙 충돌 가능 → 계층 롤업은 `rack_path`+parse_hierarchy로.
- compute_bom 재사용 시 release 필터/누적 합산의 정렬(릴리즈명 정렬) 일관성 주의.
- 대시보드가 대형 트리에서 느릴 수 있음 → path 스코프로 한정, 인덱스 재사용.
