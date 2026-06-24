# 2026-06-24 — 메인→존→배치 흐름 + 선택 집계 투자 리포트

## Context
사용자가 원하는 제품 흐름: ① 메인 = 오퍼링/리전/존 요약(존별 랙·서버 수, CAPEX) → ② 존
클릭 = 그 존의 장비 리스트 + 랙 실장도 → ③ 배치 화면은 스크롤로 줌되는 실장도 → ④ 별도
리포트에서 존/리전/오퍼링/랙타입별로 투자비·서버 수를 선택 집계. 기존엔 현황(dashboard)·
목록(placed)·랙구성도(layout)가 따로 있었지만 이 진입 흐름과 선택형 롤업이 없었다.

## Decision
하나의 집계 엔드포인트 + 3개 화면 + 에디터 보강으로 흐름을 만든다.

- **`bombom/overview.py` `build_overview`** — `placed_rows`(BOM 라인아이템, 계층 태그 포함)에서
  오퍼링/리전/존 중첩 트리와 4개 group-by(offering/region/zone/rack_type) 롤업을 한 번에 산출.
  지표: 랙 수(고유 랙), 서버 수(category=='server'), 전체 장비 수, CAPEX(priced 합), Rack-Type 수.
  대시보드/BOM과 수치 일치(같은 엔진). `GET /api/overview?path=`.
- **`web/home.html` (메인, `/home`)** — 총계 + 오퍼링→리전→존 카드. 각 존 카드는 랙/서버/장비/
  Rack-Type 수 + CAPEX, 클릭 시 `/zone?path=`.
- **`web/zone.html` (`/zone?path=`)** — 존 요약 헤더 + 좌측 장비 리스트(placed) + 우측 랙
  실장도(layout SVG)에 **휠 줌 + 드래그 팬**.
- **`web/summary.html` (투자 리포트, `/summary`)** — 집계 단위 토글(오퍼링/리전/존/랙타입별),
  투자비·서버·장비·랙·Rack-Type 표 + 합계 + 정렬. 같은 `/api/overview` 응답을 클라이언트에서 재구성.
- **`web/editor.html`** — 배치 실장도에 휠 줌 추가(기존 슬라이더 유지). 에디터는 re-render 방식
  줌이라 휠 delta로 `setZoom` 호출 후 커서 U 기준으로 스크롤 보정.
- 정적 데모(`build_static_app.py`): `/api/overview`·`/api/tree?path=`·`/api/rack?path=<file>`
  추가 캡처, 새 3페이지 포함, **index.html = home(메인)**, 배너 링크를 메인/리포트/현황/뷰어/
  에디터로 갱신.

## Consequences
- 메인에서 존을 골라 들어가 장비·실장도를 보고, 별도 리포트에서 임의 단위로 투자비를 모으는
  흐름이 한 벌로 완성. 서버 모드(`bombom serve`)와 정적 데모 양쪽에서 동작.
- 카운트/CAPEX는 단일 `build_overview`로 일원화 → 대시보드와 항상 일치.
- **Scope OUT**: 리포트의 경로 스코프 필터(현재 전체 트리 고정), 메인의 릴리즈 필터, 존 페이지의
  장비 클릭→상세(랙구성도 layout엔 있음), CSV/PDF 내보내기(정적 데모에선 비활성).
