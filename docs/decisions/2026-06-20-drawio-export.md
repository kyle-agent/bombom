# 2026-06-20 — 랙 실장도 draw.io(.drawio) export

## Context
디자이너는 화면(`/edit`·`/`)에서 NetBox 스타일 랙 실장도를 보지만, 검토·문서화 단계에서는
**편집 가능한 다이어그램**으로 들고 나가야 한다(존 전체 실장도를 한 장에 모아 주석·재배치).
기존 export는 정적 SVG(`/api/rack/elevation.svg`, 단일 랙)와 standalone HTML 보고서뿐이라
내보낸 뒤 손댈 수 없었다. 사용자는 "랙 실장도를 draw.io 형태로 export"를 요청했고, 범위는
**AZ/Rack-Type 전체 한 캔버스 + 편집 가능한 도형**으로 골랐다.

## Decision
draw.io 네이티브 포맷(`.drawio` = mxGraph XML)으로 내보낸다. PNG/PDF 같은 평면 이미지나
SVG 임베드가 아니라 **편집 가능한 vertex 셀**로 굽는다.

- **렌더러** `render/drawio.py::rack_elevation_drawio(racks, catalog, …)`: SVG 렌더러
  (`render/svg.py`)와 **같은 U→픽셀 지오메트리·카테고리 색**(`_CAT_FILL` 재사용)을 쓰되
  `<rect>` 대신 `<mxCell vertex>`을 찍는다. 화면과 export가 어긋나지 않도록 상수/색을 공유한다.
- **랙 = 이동 가능한 container, 장비 = 그 자식 셀**: 각 랙은 `container=1` 프레임이고 장비
  박스는 `parent=<frame>`·상대좌표라, draw.io에서 랙을 통째로 끌어도 장비가 함께 움직인다.
- **여러 랙 = 한 캔버스, 좌→우**: `path`가 가리키는 서브트리(존/Rack-Type/단일 랙) 아래 모든
  랙을 `load_racks`로 모아 `r.path` 정렬 후 열(column)로 나열한다. 엔드포인트 하나가 세 단위를
  모두 처리한다.
- **엔드포인트** `GET /api/rack/elevation.drawio?path=&release=&download=`: `application/xml`
  반환, `download=1`이면 `Content-Disposition: attachment`로 `<노드이름>.drawio` 저장.
  `release`가 주어지면 해당 릴리즈 장비를 앰버 외곽선으로 강조(SVG와 동일 규칙).
- **UI 진입점**은 `/manage`: 존 헤드(=AZ 전체)와 Rack-Type 칩에 `⬇ draw.io` 링크. 계층 ctx →
  `offerings/…/rack-types/<rt>` 경로를 만들어 download URL로 건다. 랙이 0개면 링크를 숨긴다.

## Consequences
- 내보낸 다이어그램을 diagrams.net/VS Code draw.io 확장에서 열어 장비 박스를 이동·주석·재색칠
  가능. 좌표가 살아있어 깨지지 않는다.
- SVG 렌더러와 지오메트리 로직이 둘로 갈렸다. 한쪽만 바뀌면 화면≠export가 될 수 있어 색/U픽셀
  같은 공유 상수는 `svg.py`에서 import해 단일 출처를 유지한다.
- **Scope OUT(v1)**: 후면(rear) 뷰, 케이블/연결선, custom line item(물리 위치 없음), 페이지
  자동 분할(랙이 매우 많으면 한 페이지가 넓어짐), draw.io 파일 round-trip 재가져오기.
