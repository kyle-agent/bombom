# 2026-06-23 — 인터랙티브 랙구성도 뷰 (`/layout`, 줌/팬/클릭상세)

## Context
디자이너가 한 존/Rack-Type의 **여러 랙을 한 화면에서** 보고 싶어 했고, 참고 UI처럼 마우스
휠 줌·드래그 이동·맞춤(fit)·장비 클릭 상세가 되길 원했다. 기존 뷰어는 랙 하나만 CSS scale
슬라이더로 확대했고, 여러 랙을 펼쳐 탐색하는 화면은 없었다. 앞서 추가한 draw.io 내보내기는
"편집용 산출물"이고, 이 뷰는 "화면에서 빠르게 둘러보기"라 둘이 짝을 이룬다.

## Decision
새 페이지 `/layout?path=`를 추가한다. 경로 하위 모든 랙을 좌→우로 펼치고 줌/팬/클릭상세를
제공한다. 서버 SVG 렌더러를 그대로 재사용한다.

- **렌더링 재사용**: `/api/layout?path=`가 `load_racks` 하위 모든 랙을 `rack_elevation_svg`로
  굽어 `{rack_id, hierarchy, rack_model, rack_u, svg}` 리스트로 반환한다. 새 그리기 로직 없음 —
  화면(뷰어/구성도)과 export(draw.io)가 같은 U→픽셀·카테고리 색을 공유한다.
- **줌/팬은 CSS transform**: scene에 `translate()+scale()`만 적용(라이브러리 0개). 휠 줌은
  **커서 위치 기준**(map 류 UX), 드래그=팬, 더블클릭=확대, +/−/맞춤/100% 버튼.
- **클릭상세는 `pointerup`에서 처리**(중요): 부드러운 드래그를 위해 `setPointerCapture`를 쓰는데,
  포인터 캡처는 내부 SVG 요소의 합성 `click` 이벤트를 **억제**한다. 그래서 별도 click 리스너
  대신 pointerup에서 이동거리 임계값(>4px)으로 탭/드래그를 구분하고, 탭이면
  `elementFromPoint(...).closest('.dev')`로 장비를 찾아 패널을 연다.
- **클릭 타깃 데이터**: `render/svg.py`가 각 장비 `<g>`에 `class="dev"` + `data-device/model/
  pos/span/rel/cat`를 실어 보낸다(추가만, 기존 동작 불변). 패널이 이 dataset을 읽는다.
- **진입점**: 뷰어의 랙 헤더에 "🗺 존 전체 구성도"(현재 랙의 존 경로로), `/manage`의 존·
  Rack-Type 칩에 "🗺 구성도"(draw.io 옆). 둘 다 `?path=`로 스코프를 넘긴다.

## Consequences
- 여러 랙을 한 캔버스에서 줌/팬으로 탐색 + 장비 클릭 상세까지 가능. draw.io 내보내기와 한 쌍.
- SVG 렌더러에 data 속성이 생겨, 뷰어/에디터에서도 같은 클릭상세를 붙일 여지가 생겼다.
- **Scope OUT(v1)**: 가격/평가일을 상세 패널에 표시(pricebook 조회 필요), 빈 U·랙 접기(참고
  UI의 전체 접기/펼치기), 후면 뷰, 드래그로 배치 편집(이 뷰는 읽기 전용). `/layout`은 IA 감사에서
  지적된 nav 일관성 문제를 그대로 안고 추가됨 — 공유 헤더 리팩터 때 함께 정리.
